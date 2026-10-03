# Interview Guide — AI Resume Screening System

This guide teaches the project concept-by-concept so you can explain **any** part of it confidently in a Data Science / ML / GenAI interview. Read it alongside the actual source files — every section points to the file where the concept is implemented.

---

## 1. Python Concepts Used

| Concept | Where | Why it matters here |
|---|---|---|
| **File handling / `pathlib`** | `document_reader.py`, `config.py` | `Path` objects instead of raw strings make paths cross-platform and let us safely resolve/validate them (path-traversal guard in `screening_service._resolve_path`). |
| **Functions** | everywhere | Small, single-purpose functions (`lowercase`, `tokenize`, `remove_stopwords`) make the pipeline composable and independently testable. |
| **Classes / dataclasses** | `CleanedText`, `SkillExtractionResult`, `TfidfMatchResult`, `ExperienceMatchResult`, `ATSScoreBreakdown` | `@dataclass` gives typed, self-documenting return values instead of returning bare tuples or dicts. |
| **Abstract base classes** | `DocumentReader(ABC)` in `document_reader.py` | Defines a contract (`read(path) -> str`) that future `PdfDocumentReader`/`DocxDocumentReader` implementations must follow — this is the Open/Closed Principle: open for extension, closed for modification. |
| **Type hints** | function signatures throughout | `list[str]`, `set[str]`, `float | None` — self-documenting and catch bugs early with a type checker. |
| **Exception handling** | `DocumentReadError`, `TfidfMatchError`, `ScreeningError`, `ScoringConfigError` | Custom exception classes per layer let the API translate failures into meaningful HTTP status codes instead of leaking stack traces. |
| **Logging** | `utils/logger.py`, used in every module | Structured, leveled logs (`INFO`/`ERROR`) instead of `print()` — production code needs to be observable. |
| **Modular programming** | package layout (`preprocessing/`, `extraction/`, `matching/`, `services/`, `schemas/`) | Each package has one responsibility; `screening_service.py` orchestrates without knowing *how* each stage works internally. |
| **Sets, dicts, list comprehensions** | `skill_extractor.py`, `scoring.py` | Skill matching is naturally a **set intersection/difference** problem (`jd_skills & resume_skills`, `jd_skills - resume_skills`) — sets give O(1) membership checks and make "matched"/"missing" trivial one-liners. |

---

## 2. NLP Fundamentals

- **Corpus**: the full collection of documents being analyzed. In `compute_text_similarity`, the "corpus" is just the 2-document pair `[jd_text, resume_text]` passed to `TfidfVectorizer.fit_transform`.
- **Document**: one unit of text — here, one JD or one resume.
- **Tokens**: the individual units (usually words) a document is split into. Produced by `tokenize()` in `text_cleaner.py`.
- **Vocabulary**: the set of all unique tokens across the corpus. `TfidfVectorizer` builds this automatically from the fitted documents.
- **Tokenization**: splitting raw text into tokens (here, simple whitespace splitting after cleaning — no need for a heavier tokenizer since the text is already normalized).
- **Stopwords**: very common words ("the", "is", "and") that carry little distinguishing meaning and are usually removed before analysis. See `STOPWORDS` in `text_cleaner.py`.
- **Lemmatization**: reducing a word to its base/dictionary form (e.g. "running" → "run"). This project uses a **lightweight, rule-based** approach (suffix stripping) rather than a full lemmatizer like spaCy, to keep the project dependency-free — with an explicit exclusion list (`_LEMMA_EXCLUDE`) so it never mangles short acronyms like "sql" or "aws".
- **Keyword extraction**: identifying the "important" terms in a document. Here, done by taking the cleaned tokens of the JD and filtering out a generic stopword-like list (`GENERIC_STOP_KEYWORDS`) — see `extract_keywords_from_jd` in `scoring.py`.
- **Text normalization**: the umbrella term for lowercasing, punctuation removal, and whitespace collapsing that make two pieces of text comparable regardless of superficial formatting differences.

---

## 3. TF-IDF — Formulas and a Worked Example

### Term Frequency (TF)

```
TF(term, doc) = (number of times term appears in doc) / (total terms in doc)
```

### Inverse Document Frequency (IDF)

```
IDF(term, corpus) = log( (1 + N) / (1 + df(term)) ) + 1
```
where `N` = total number of documents, `df(term)` = number of documents containing the term. (This is scikit-learn's smoothed formula — the `+1`s prevent division by zero.)

### TF-IDF

```
TF-IDF(term, doc) = TF(term, doc) × IDF(term, corpus)
```

### Numeric example

Corpus of 2 documents:
- **Doc A (JD)**: "python sql python machine learning"
- **Doc B (Resume)**: "python sql java"

Vocabulary: `{python, sql, machine, learning, java}`

- `TF("python", A)` = 2/5 = 0.4
- `df("python")` = 2 (appears in both docs) → `IDF("python")` = low (common across corpus)
- `df("machine")` = 1 (only in Doc A) → `IDF("machine")` = higher (distinctive)

So "machine" gets a **higher TF-IDF weight** in Doc A than "python" does, even though "python" appears more often — because "machine" is more *distinctive* to that document relative to the corpus. This is the entire point of TF-IDF: raw frequency alone (as in `CountVectorizer`) would over-weight common words; TF-IDF corrects for that.

### Why TF-IDF instead of `CountVectorizer`?

`CountVectorizer` just counts raw word occurrences. Two JDs that both repeat the word "experience" ten times would look very similar to `CountVectorizer` even if they're for completely different roles. TF-IDF down-weights words that are common across many documents (like "experience", "team", "role") and up-weights the words that are actually distinctive to a specific JD or resume (like "PySpark" or "SBERT").

---

## 4. Cosine Similarity

**What it is**: the cosine of the angle between two vectors.

```
cosine_similarity(A, B) = (A · B) / (‖A‖ × ‖B‖)
```

- **What it is**: TF-IDF turns each document into a high-dimensional vector where each dimension is a vocabulary term. Cosine similarity measures how similar the *direction* of two such vectors is.
- **Why cosine similarity**: it's insensitive to document *length* (magnitude). A 3-page resume and a 1-paragraph JD can still have vectors pointing in a very similar *direction* if they emphasize the same proportion of relevant terms.
- **Why not Euclidean distance**: Euclidean distance is sensitive to vector magnitude, i.e. document length. A longer document naturally produces a "farther" point in vector space even if its word *proportions* are identical to a shorter one — that would unfairly penalize longer resumes.
- **When documents are similar**: cosine similarity approaches **1** (vectors point in nearly the same direction — same words, similar proportions).
- **When documents are completely different**: cosine similarity approaches **0** (no shared vocabulary at all — orthogonal vectors).

Both boundary cases are directly asserted in `tests/test_matching.py` (`test_identical_documents_have_similarity_one`, `test_completely_different_documents_have_low_similarity`).

---

## 5. Scikit-learn

- **`TfidfVectorizer`**: converts a list of raw text documents into a sparse TF-IDF matrix. Used in `tfidf_matcher.py` with default settings — `fit_transform([jd_text, resume_text])` fits vocabulary and IDF weights on both documents together, then transforms them into vectors in the same space so they're directly comparable.
- **`cosine_similarity`**: from `sklearn.metrics.pairwise`, takes two matrices/vectors and returns their pairwise cosine similarities.
- **Sparse matrix**: `TfidfVectorizer` returns a `scipy.sparse` matrix, not a dense NumPy array, because most vocabulary terms don't appear in most documents — storing only non-zero entries is far more memory-efficient for real-world vocabularies.
- **Pipeline**: not used here (the flow is simple enough to call `fit_transform` directly), but in a larger system you'd wrap vectorization + a downstream estimator in an `sklearn.pipeline.Pipeline` to avoid data leakage between train/test splits and to serialize the whole flow as one object.
- **Train/test split — why not needed here**: this project has **no trained supervised model**. There's no `.fit()` on labeled hiring outcomes and therefore no train/test split to reason about. `TfidfVectorizer.fit_transform` "fits" only in the sense of building a vocabulary from the two documents being compared *at request time* — it is not a model being trained on historical data. This is a deliberate scope boundary, not an oversight — see README "Limitations" and "Future Enhancements" for how a *learned* model would change this.

---

## 6. ATS Scoring — How the Four Components Become One Score

```
ATS Score = text_similarity_score   × 0.50
          + skill_match_score        × 0.30
          + experience_match_score   × 0.10
          + keyword_match_score      × 0.10
```

Walk through it component by component:

1. **text_similarity_score** (50%): `cosine_similarity(JD_vector, Resume_vector) × 100`. The single largest signal — captures overall lexical overlap.
2. **skill_match_score** (30%): `(matched_skills / jd_skills) × 100` from the dictionary lookup. Captures whether the *specific named technologies* the JD asks for are present.
3. **experience_match_score** (10%): 100 if candidate years ≥ required years; otherwise `(candidate / required) × 100`. A smaller weight because it's a single noisy regex extraction, not a rich signal.
4. **keyword_match_score** (10%): `(matched_keywords / jd_keywords) × 100` after filtering generic filler words. A smaller, complementary signal that rewards echoing the JD's specific vocabulary beyond just the skill dictionary.

Each is pre-normalized to 0–100 *before* weighting, so the weights genuinely represent "how much this factor matters" rather than being distorted by components living on different scales. All of this lives in `compute_ats_score()` in `scoring.py`, and the weights themselves live in `config.SCORING_WEIGHTS` so they can be tuned without touching scoring logic.

---

## 7. FastAPI

- **FastAPI**: a modern Python web framework built on Starlette + Pydantic, chosen here for automatic request/response validation and auto-generated OpenAPI docs.
- **REST API**: an architectural style where resources (here: screening results, job lists, resume lists) are accessed via standard HTTP methods and URLs.
- **HTTP methods used**: `GET` for read-only operations (`/health`, `/jobs`, `/resumes`), `POST` for operations that do work / could have side effects (`/screen`, `/screen/batch`, `/reload`).
- **Request / Response**: FastAPI parses incoming query params/JSON bodies into typed Python objects, and serializes return values (here, Pydantic models like `ScreenResult`) back into JSON automatically.
- **Pydantic**: the data-validation library FastAPI is built on. `schemas/response_models.py` defines typed models (`ScreenResult`, `BatchScreenResponse`, etc.) so every field's type is enforced and documented automatically.
- **Validation**: happens automatically from the Pydantic models and function type hints — e.g. `resume_files: list[str]` on `/screen/batch` means FastAPI rejects a request where that's not a JSON array of strings, before your code even runs.
- **HTTP status codes used**: `200` (success), `400` (bad request — missing required params), `422` (unprocessable — screening failed, e.g. file not found or empty vocabulary).
- **Swagger / OpenAPI**: FastAPI auto-generates an interactive API explorer at `/docs` (Swagger UI) and a machine-readable spec at `/openapi.json`, directly from the route definitions and Pydantic models — no extra work required.

---

## 8. Software Architecture (Layered Pipeline)

```
Input
  ↓
File Reader          (extraction/document_reader.py)
  ↓
Text Preprocessor     (preprocessing/text_cleaner.py)
  ↓
Skill Extractor       (extraction/skill_extractor.py)
  ↓
Feature Extraction     (matching/scoring.py — experience & keyword extraction)
  ↓
TF-IDF                (matching/tfidf_matcher.py)
  ↓
Cosine Similarity      (matching/tfidf_matcher.py)
  ↓
Scoring Engine         (matching/scoring.py — compute_ats_score)
  ↓
Response Schema        (schemas/response_models.py)
  ↓
FastAPI                (main.py)
```

`services/screening_service.py` is the **orchestrator** — it doesn't implement any NLP or scoring logic itself, it just calls each layer in order and assembles the final `ScreenResult`. This separation means each layer can be unit-tested in isolation (see `tests/test_preprocessing.py`, `tests/test_matching.py`) independently of the API layer, which gets its own integration tests (`tests/test_api.py`).

---

## 9. Key Design Decisions (and Why)

| Decision | Why |
|---|---|
| Protect technology tokens (`C++`, `.NET`, `scikit-learn`) before stripping punctuation | Blind punctuation removal would destroy meaningful technology names — directly hurts skill extraction accuracy. |
| Dictionary-based skill extraction instead of a trained NER model | 100% reproducible and auditable — every match traces to a literal config entry, which is essential for an *explainable* ATS score. |
| Rule-based experience-years regex instead of an ML model | Same reasoning — a recruiter or candidate can verify the exact number extracted by reading the sentence it came from. |
| ATS score = weighted combination of 4 components, not `cosine_similarity × 100` | A single similarity number conflates "uses similar words" with "has the right skills/experience" — separating them into weighted, independently-inspectable components is what makes the score explainable and tunable. |
| `SCORING_WEIGHTS` validated to sum to 1.0 at import time | Fails fast at startup instead of silently producing a miscalibrated score if someone edits the config incorrectly. |
| `DocumentReader` abstract interface with only a TXT implementation today | Lets PDF/DOCX support be added later (`PdfDocumentReader`, `DocxDocumentReader`) without touching any downstream pipeline code — Open/Closed Principle. |
| Custom exception classes per layer (`DocumentReadError`, `TfidfMatchError`, `ScreeningError`) | Lets the FastAPI layer translate failures into clean HTTP responses (422) instead of leaking raw stack traces to API consumers. |
| Path-traversal guard in `_resolve_path` | The API takes filenames as input — without validation, a malicious `../../etc/passwd`-style filename could escape the intended data directory. |
| Skill/keyword match default to 100% when the JD lists zero skills/keywords | Avoids division by zero and avoids unfairly penalizing a candidate for a JD that wasn't well skill-tagged. |

---

## 10. Limitations (Interview-Ready Version)

- TF-IDF is **lexical, not semantic** — no understanding of synonyms or paraphrasing.
- No synonym recognition (e.g. "Postgres" vs "PostgreSQL").
- Resume formatting (tables, columns, headers) can affect text extraction in real-world PDF/DOCX resumes (not exercised here, since input is TXT-only).
- The skill dictionary requires ongoing manual maintenance — anything not listed is invisible to the system.
- Rule-based experience extraction only reliably captures the *first* "N years" style mention.
- **The ATS score is a screening heuristic, not a validated hiring-probability model** — it has not been trained or evaluated against real hiring outcomes.
- Bias can enter via the skill dictionary, the generic-keyword filter list, or the scoring weights themselves, since all three are human-authored.

---

## 11. Future Enhancements (Deep Dive)

1. **Sentence Transformers / SBERT** — replace or augment TF-IDF with dense sentence embeddings for true semantic similarity (captures "ML" ≈ "machine learning").
2. **BERT** — contextual token embeddings for finer-grained understanding of resume/JD phrasing.
3. **Named Entity Recognition (NER)** — extract skills, job titles, and organizations more flexibly than a fixed dictionary.
4. **LLM-based resume parsing** — handle free-form, unstructured resumes (varied section orders, non-standard formatting) far more robustly than regex/dictionary rules.
5. **Vector databases** (e.g. Pinecone, FAISS, pgvector) — store embeddings for thousands of resumes and query efficiently at scale.
6. **Semantic search** — let a recruiter search "find candidates similar to this JD" across a large resume pool using embedding similarity.
7. **RAG (Retrieval-Augmented Generation)** — let a recruiter ask natural-language questions about a candidate pool, grounded in retrieved resume content.
8. **PDF/DOCX parsing** — implement `PdfDocumentReader` (`pypdf`) and `DocxDocumentReader` (`python-docx`) against the existing `DocumentReader` interface.
9. **Streamlit/React frontend** — a UI on top of the existing FastAPI backend for non-technical recruiters.
10. **Docker deployment** — containerize the FastAPI app for consistent, portable deployment.
11. **Cloud deployment** — deploy to AWS/GCP/Azure with autoscaling for real screening volumes.

---

## 12. Common Mistakes to Avoid (and that this project avoids)

- ❌ Randomly generating a score instead of computing it — this project's score is **fully reproducible**: same inputs always produce the same output.
- ❌ Blindly stripping all punctuation and destroying technology names like `C++`/`.NET`.
- ❌ Multiplying cosine similarity by 100 and calling it "the ATS score" — conflates lexical similarity with actual fit.
- ❌ Claiming TF-IDF provides "semantic understanding" — it doesn't; be precise about this distinction in an interview.
- ❌ Hardcoding scoring weights inline across multiple files instead of one validated config.
- ❌ Not handling the empty-vocabulary / empty-file / missing-file edge cases — this project raises specific, typed exceptions for each and maps them to proper HTTP status codes.
- ❌ Logging full resume text at INFO level (a privacy concern) — this project logs only metadata (filenames, character counts, scores).
