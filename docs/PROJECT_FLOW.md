# Project Flow & Debugging Guide

This document exists for one purpose: when something breaks, you should be able to open this file, find the stage that's misbehaving, and go straight to the right file and line — without re-reading the whole codebase.

It covers: the end-to-end request flow, exactly which file/function owns each step, what each step receives and returns, where every exception type is raised and caught, how to reproduce any stage in isolation, and a symptom → cause → file lookup table.

---

## 1. The One Picture to Remember

```
┌─────────────────────────────────────────────────────────────────────────┐
│  HTTP request (POST /screen or /screen/batch)                           │
│  src/main.py                                                            │
└───────────────────────────────┬───────────────────────────────────────┘
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  screen_resume(jd_file, resume_file)                                    │
│  src/services/screening_service.py   ◄── THE ORCHESTRATOR               │
│  Every stage below is called from inside this one function, in order.  │
└───────────────────────────────┬───────────────────────────────────────┘
                                 ▼
   ┌─────────────────────────────────────────────────────────────┐
   │ STEP A — resolve + read files                                │
   │ _resolve_path()            → path-traversal guard            │
   │ read_document()             → src/extraction/document_reader.py │
   │ raises: DocumentReadError                                    │
   └─────────────────────────────┬─────────────────────────────────┘
                                  ▼
   ┌─────────────────────────────────────────────────────────────┐
   │ STEP B — clean text                                          │
   │ clean_text()                → src/preprocessing/text_cleaner.py │
   │ returns: CleanedText(raw_text, cleaned_text, tokens)         │
   └─────────────────────────────┬─────────────────────────────────┘
                                  ▼
   ┌─────────────────────────────────────────────────────────────┐
   │ STEP C — text similarity                                     │
   │ compute_text_similarity()   → src/matching/tfidf_matcher.py  │
   │ raises: TfidfMatchError                                      │
   │ returns: TfidfMatchResult(similarity_score, similarity_pct)  │
   └─────────────────────────────┬─────────────────────────────────┘
                                  ▼
   ┌─────────────────────────────────────────────────────────────┐
   │ STEP D — skill matching                                      │
   │ extract_skills() × 2        → src/extraction/skill_extractor.py │
   │ compare_skills()                                              │
   └─────────────────────────────┬─────────────────────────────────┘
                                  ▼
   ┌─────────────────────────────────────────────────────────────┐
   │ STEP E — experience matching                                 │
   │ extract_experience_match()  → src/matching/scoring.py        │
   └─────────────────────────────┬─────────────────────────────────┘
                                  ▼
   ┌─────────────────────────────────────────────────────────────┐
   │ STEP F — keyword matching                                    │
   │ compute_keyword_match()     → src/matching/scoring.py        │
   └─────────────────────────────┬─────────────────────────────────┘
                                  ▼
   ┌─────────────────────────────────────────────────────────────┐
   │ STEP G — final weighted score                                │
   │ compute_ats_score()         → src/matching/scoring.py        │
   │ raises (at import time, not per-request): ScoringConfigError │
   │ returns: ATSScoreBreakdown                                   │
   └─────────────────────────────┬─────────────────────────────────┘
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  ScreenResult assembled and returned                                    │
│  src/schemas/response_models.py  (Pydantic model — validates on output) │
└───────────────────────────────┬───────────────────────────────────────┘
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  FastAPI serializes ScreenResult → JSON response                        │
│  src/main.py                                                            │
└─────────────────────────────────────────────────────────────────────────┘
```

`/screen/batch` is the same flow, just looped once per resume by `screen_batch()` in `screening_service.py`, with per-resume failures caught and collected into an `errors` list instead of aborting the whole batch.

---

## 2. File-by-File: What Calls What

| File | Role | Called by | Calls |
|---|---|---|---|
| `src/main.py` | FastAPI routes + exception → HTTP status mapping | uvicorn | `screening_service.py` functions |
| `src/services/screening_service.py` | **Orchestrator.** No NLP/scoring logic of its own — just calls the pipeline in order. | `main.py` | `document_reader.py`, `text_cleaner.py`, `skill_extractor.py`, `tfidf_matcher.py`, `scoring.py` |
| `src/extraction/document_reader.py` | Reads a file off disk into raw text | `screening_service.py` | — (leaf module) |
| `src/preprocessing/text_cleaner.py` | Raw text → cleaned text + tokens | `screening_service.py` | — (leaf module) |
| `src/extraction/skill_extractor.py` | Cleaned text → set of detected skills; compares two sets | `screening_service.py` | `config.py` (reads `TECHNICAL_SKILLS`) |
| `src/matching/tfidf_matcher.py` | Two cleaned texts → cosine similarity | `screening_service.py` | scikit-learn |
| `src/matching/scoring.py` | Experience extraction, keyword extraction, final weighted score | `screening_service.py` | `config.py` (reads `SCORING_WEIGHTS`, `SCORE_THRESHOLDS`, `GENERIC_STOP_KEYWORDS`) |
| `src/schemas/response_models.py` | Pydantic response/request shapes | `main.py`, `screening_service.py` | — (leaf module) |
| `src/config.py` | **Single source of truth** for every weight, threshold, path, and skill list | everything above | — (leaf module, imported everywhere) |
| `src/utils/logger.py` | One shared logger factory | every module above | — (leaf module) |

**Rule of thumb:** data only ever flows *downward* through this table — `main.py` never talks to `tfidf_matcher.py` directly, it always goes through `screening_service.py`. If you ever see `main.py` importing from `matching/` or `extraction/` directly, that's a sign the architecture has been bypassed — fix it by routing through `screening_service.py` instead.

---

## 3. Data Shape at Each Hop

Tracing `screen_resume("data_scientist.txt", "candidate_01.txt")` step by step:

```
"data_scientist.txt", "candidate_01.txt"          (filenames, str)
        │  _resolve_path()
        ▼
Path(".../data/job_descriptions/data_scientist.txt"), Path(".../data/resumes/candidate_01.txt")
        │  read_document()
        ▼
jd_raw: str, resume_raw: str                        (raw file contents)
        │  clean_text()
        ▼
jd_cleaned: CleanedText, resume_cleaned: CleanedText
    .raw_text      -> original string
    .cleaned_text  -> lowercased, punctuation-stripped, space-joined string
    .tokens        -> list[str]
        │  compute_text_similarity(jd_cleaned.cleaned_text, resume_cleaned.cleaned_text)
        ▼
TfidfMatchResult(similarity_score: float[0-1], similarity_percentage: float[0-100])
        │  extract_skills(...) ×2, compare_skills(...)
        ▼
dict: {jd_skills, resume_skills, matched_skills, missing_skills, skill_match_percentage}
        │  extract_experience_match(jd_raw, resume_raw)
        ▼
ExperienceMatchResult(required_experience_years, candidate_experience_years, experience_match_score)
        │  compute_keyword_match(jd_cleaned.tokens, resume_cleaned.tokens)
        ▼
KeywordMatchResult(jd_keywords, matched_keywords, missing_keywords, keyword_match_percentage)
        │  compute_ats_score(...)
        ▼
ATSScoreBreakdown(ats_score, text_similarity_score, skill_match_score,
                   experience_match_score, keyword_match_score, recommendation)
        │  assembled into
        ▼
ScreenResult   (Pydantic model — this is what gets JSON-serialized back to the client)
```

If a bug shows up in the final JSON, work **backward** through this list: check the dataclass/field one step before it in the chain, and keep stepping back until the value looks wrong — that's the stage at fault.

---

## 4. Where Every Exception Comes From

| Exception | Raised in | Caught in | Becomes |
|---|---|---|---|
| `DocumentReadError` | `document_reader.py` — missing file, wrong extension, empty file, bad encoding | `screening_service.py` → re-raised as `ScreeningError` | HTTP 422 |
| `TfidfMatchError` | `tfidf_matcher.py` — empty text, empty TF-IDF vocabulary | `screening_service.py` → re-raised as `ScreeningError` | HTTP 422 |
| `ScreeningError` | `screening_service.py` — the above, plus path-traversal guard, plus "no usable text after cleaning" | `main.py`'s `@app.exception_handler(ScreeningError)` AND explicit `try/except` in the `/screen` route | HTTP 422 with `{"detail": "..."}` |
| `ScoringConfigError` | `scoring.py` — `SCORING_WEIGHTS` doesn't sum to 1.0 | **nowhere — intentional.** This runs once at import time (`_validate_weights()` is called at module load), so a misconfigured weight crashes the app at **startup**, not mid-request. | App fails to start; fix `config.py` |

**Debugging tip:** if you're getting a generic HTTP 500 instead of a clean 422 with a message, it means an exception type that ISN'T in this table was raised somewhere — search the traceback for the file, then check whether that file's errors are being wrapped correctly (every leaf module should raise its own typed exception, and `screening_service.py` should be the only place that translates those into `ScreeningError`).

---

## 5. How to Reproduce Any Single Stage in Isolation

You don't need to run the full API to debug one stage. Activate the venv (`source venv/bin/activate`, or `venv\Scripts\activate.bat` on Windows) and drop into a Python shell with `PYTHONPATH=.`:

```python
# Stage B — preprocessing only
from src.preprocessing.text_cleaner import clean_text
result = clean_text("Experience with Python, SQL and scikit-learn.")
print(result.tokens)

# Stage C — TF-IDF similarity only
from src.matching.tfidf_matcher import compute_text_similarity
r = compute_text_similarity("python sql machine learning", "python sql java")
print(r.similarity_score, r.similarity_percentage)

# Stage D — skills only
from src.extraction.skill_extractor import extract_skills, compare_skills
jd = extract_skills("python sql aws machine learning")
resume = extract_skills("python sql")
print(compare_skills(jd.found_skills, resume.found_skills))

# Stage E — experience only
from src.matching.scoring import extract_experience_match
print(extract_experience_match("3+ years required", "I have 2 years experience"))

# Full pipeline, skipping the HTTP layer entirely
from src.services.screening_service import screen_resume
print(screen_resume("data_scientist.txt", "candidate_01.txt"))
```

This is the fastest way to binary-search a bug: run the full pipeline, see which field looks wrong, then call that one stage directly with the same input to confirm.

---

## 6. Logging — What You'll See and Where

Every module logs through `src/utils/logger.py` with `INFO` as the default level. A single `/screen` request produces a log sequence like this (file/function in brackets added here for clarity — the real logs don't include them, use the **logger name**, which IS the module path, to tell them apart):

```
INFO | src.services.screening_service | Screening resume 'candidate_01.txt' against JD 'data_scientist.txt'
INFO | src.extraction.document_reader | Read file 'data_scientist.txt' (1331 characters)
INFO | src.extraction.document_reader | Read file 'candidate_01.txt' (1156 characters)
INFO | src.matching.tfidf_matcher     | Computed TF-IDF cosine similarity: 0.5654
INFO | src.extraction.skill_extractor | Extracted 20 skills
INFO | src.extraction.skill_extractor | Extracted 20 skills
INFO | src.matching.scoring            | Experience match: required=3.0 candidate=3.5 score=100.00
INFO | src.matching.scoring            | Final ATS score: 78.04 (Moderate Match)
```

Because the logger name is always the module's `__name__`, **the second column of every log line tells you exactly which file to open.** If a request fails, the log sequence stops right after the last successful stage — the next stage in the pipeline (Section 1's diagram) is where the problem is.

Resume/JD **content** is deliberately never logged (only filenames and character counts) — don't add `logger.info(resume_raw)` style lines; if you need to see actual content while debugging, use `print()` locally and remove it before committing.

---

## 7. Symptom → Likely Cause → File to Check

| Symptom | Likely cause | Check this file/function |
|---|---|---|
| `422 "File not found"` | Wrong filename, or file not in `data/job_descriptions/` or `data/resumes/` | `document_reader.py::TxtDocumentReader.read` |
| `422 "File is empty"` | The `.txt` file has no content (or only whitespace) | the actual data file; also `document_reader.py` |
| `422 "TF-IDF vocabulary is empty"` | Both documents, after cleaning, contained only stopwords/punctuation — e.g. a resume that's just a table of numbers | `tfidf_matcher.py::compute_text_similarity`; inspect `clean_text(...).tokens` for that file |
| `422 "Job description contains no usable text after cleaning"` | Same as above but caught earlier, before TF-IDF even runs | `screening_service.py::screen_resume` |
| Skill match is `0%` even though the resume clearly lists the skill | The skill isn't in `config.TECHNICAL_SKILLS`, OR it's phrased differently than the dictionary entry (e.g. resume says "Sklearn" but dictionary has `"scikit-learn"`) | `config.py::TECHNICAL_SKILLS`; add the missing variant |
| A technology name looks mangled in `cleaned_text` (e.g. `"c"` instead of `"c++"`) | The protect/restore step in text cleaning didn't recognize that token | `text_cleaner.py::_PROTECTED_TOKENS` — add the missing token here |
| `experience_match_score` is `0` unexpectedly | The resume doesn't contain a literal "N years" phrase near a number, or it's phrased in a way the regex doesn't catch (e.g. "Over a decade of experience") | `scoring.py::_EXPERIENCE_PATTERN` and `_extract_years` — this is a known, documented limitation (see README "Limitations") |
| `keyword_match_score` looks too strict / too lenient | The generic-word filter list is under/over-inclusive for this particular JD's phrasing | `config.py::GENERIC_STOP_KEYWORDS` |
| App won't start at all, `ScoringConfigError` at import | `SCORING_WEIGHTS` in `config.py` doesn't sum to exactly `1.0` | `config.py::SCORING_WEIGHTS` |
| `/screen/batch` returns fewer results than resumes submitted | One or more resumes failed individually — check `errors` in the raw `screen_batch()` return (not exposed in the Pydantic response, but logged) | `screening_service.py::screen_batch`; check logs for `ERROR` lines |
| Batch results aren't sorted correctly | Should never happen — sort is `reverse=True` on `ats_score` right before building `ranked_summary` | `screening_service.py::screen_batch` |
| `pip install` / `venv` issues | Python version mismatch, or stale venv | Run `./setup.sh --recreate` (or `setup.bat --recreate` on Windows) |
| Tests fail only when run a certain way | Almost always a `PYTHONPATH` issue — tests import `src.*`, which requires the project root on the path | Run exactly as documented: `PYTHONPATH=. pytest tests/ -v` |

---

## 8. Adding a New Pipeline Stage (If You Extend the Project)

If you add something new (e.g. a semantic-similarity stage using embeddings), follow the existing pattern so the next person debugging this can use this same document:

1. Put the new logic in its own leaf module (e.g. `src/matching/semantic_matcher.py`), with its own typed exception class and its own dataclass return type — don't inline it into `screening_service.py`.
2. Call it from `screening_service.py::screen_resume`, in the position in the pipeline where it logically belongs (Section 1).
3. Add any new weight/threshold to `config.py`, and if it affects `SCORING_WEIGHTS`, remember the sum-to-1.0 validation will fail fast if you forget to rebalance the others.
4. Add the new field to `ScreenResult` in `schemas/response_models.py`.
5. Add unit tests for the new module (mirroring `tests/test_matching.py`'s style: identical-input case, no-overlap case, empty-input case).
6. Update the tables in Sections 2, 3, and 4 of **this file** so debugging stays easy for the next change too.
