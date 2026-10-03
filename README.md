# AI Resume Screening System

An explainable, ATS-style resume screening system built with **Python, NLP (TF-IDF), scikit-learn and FastAPI**. It compares a job description (JD) against one or more resumes and produces a **reproducible, mathematically explainable** match score — not a randomly generated or black-box number.

---

## 1. Project Overview

Recruiters and ATS (Applicant Tracking System) tools screen large volumes of resumes against a job description. This project reproduces the core mechanics of that screening step: given a JD and a resume, it computes an **ATS Score (0–100)** made up of four transparent, individually-inspectable components, along with matched/missing skills and keywords so a candidate score can always be explained line by line.

## 2. Business Problem

Manually screening hundreds of resumes per role is slow and inconsistent between reviewers. An automated first-pass screen that is **explainable** (not a black box) lets a recruiter quickly triage and rank candidates while still being able to justify *why* a candidate scored the way they did — critical for fairness and for candidate feedback.

## 3. Solution

The system:
1. Reads a JD and resume as text.
2. Cleans and tokenizes both documents.
3. Extracts technical skills from a configurable skill dictionary.
4. Computes lexical text similarity using **TF-IDF + cosine similarity**.
5. Extracts years-of-experience mentions with a rule-based parser.
6. Extracts and compares important keywords.
7. Combines all four signals into one weighted, configurable **ATS Score**.
8. Exposes everything through a **FastAPI** service, including batch ranking of multiple resumes against one JD.

## 4. Architecture

```
Input (JD + Resume files)
        │
        ▼
  File Reader (extraction/document_reader.py)
        │
        ▼
  Text Preprocessor (preprocessing/text_cleaner.py)
        │
        ▼
  Skill Extractor (extraction/skill_extractor.py)
        │
        ▼
  TF-IDF + Cosine Similarity (matching/tfidf_matcher.py)
        │
        ▼
  Experience & Keyword Matching (matching/scoring.py)
        │
        ▼
  ATS Scoring Engine (matching/scoring.py)
        │
        ▼
  Response Schema (schemas/response_models.py)
        │
        ▼
  FastAPI (main.py)
```

Each stage is a separate, independently testable module. `screening_service.py` is the orchestration layer that wires the pipeline together for both single-resume and batch screening.

## 5. Project Structure

```
resume_screening_system/
├── data/
│   ├── job_descriptions/       # sample JD .txt files
│   └── resumes/                 # sample resume .txt files
├── src/
│   ├── config.py                 # all weights, thresholds, skill dictionary
│   ├── main.py                    # FastAPI app + endpoints
│   ├── preprocessing/text_cleaner.py
│   ├── extraction/
│   │   ├── document_reader.py     # DocumentReader interface (TXT now, PDF/DOCX-ready)
│   │   └── skill_extractor.py
│   ├── matching/
│   │   ├── tfidf_matcher.py       # TF-IDF + cosine similarity
│   │   └── scoring.py             # experience, keyword, final ATS scoring
│   ├── services/screening_service.py  # orchestration
│   ├── schemas/response_models.py     # Pydantic models
│   └── utils/logger.py
├── tests/
│   ├── test_preprocessing.py
│   ├── test_matching.py
│   └── test_api.py
├── docs/
│   ├── INTERVIEW_GUIDE.md          # concept-by-concept interview prep
│   └── PROJECT_FLOW.md             # end-to-end flow + debugging guide (read this first when something breaks)
├── venv/                            # created by setup.sh / setup.bat — NOT committed to git
├── .python-version                  # pinned Python version (3.12.10) used by setup.sh/setup.bat
├── setup.sh / setup.bat             # one-shot environment setup (installs Python + creates venv + installs deps)
├── run.sh / run.bat                 # activate venv + start the API
├── requirements.txt
└── README.md
```

**New to this codebase and something's broken?** Start with `docs/PROJECT_FLOW.md` — it has the full request-flow diagram, a symptom → cause → file lookup table, and shows how to test any single pipeline stage in isolation without running the whole API.

## 6. Installation

**Everything for this project — code, sample data, and the Python environment — lives inside this one `resume_screening_system/` folder.** It does not touch your global Python install or any packages outside this folder.

### macOS / Linux

```bash
cd resume_screening_system
chmod +x setup.sh run.sh
./setup.sh
```

`setup.sh` reads the pinned version from `.python-version` (**3.12.10**) and:
1. Uses [`pyenv`](https://github.com/pyenv/pyenv) to install exactly that Python version if `pyenv` is available (it will offer to install `pyenv` for you if it isn't).
2. Otherwise falls back to a `python3.12` already on your PATH, or warns and uses whatever `python3` resolves to.
3. Creates a virtual environment at `./venv` — **inside this project folder**.
4. Installs every dependency from `requirements.txt` into that venv.
5. Runs a quick import self-check so you know immediately if something's wrong.

Re-running `./setup.sh` is safe (it reuses the existing venv). Force a clean rebuild with `./setup.sh --recreate`.

### Windows

```bat
cd resume_screening_system
setup.bat
```

Same steps as above, using the Windows `py` launcher to get Python 3.12 and creating `venv\` inside the project folder.

### Running the API afterward

```bash
./run.sh          # macOS/Linux
run.bat           # Windows
```

Both scripts just activate `./venv` and start `uvicorn src.main:app --reload` — equivalent to the manual steps in [Section 16](#16-sample-request), but without you needing to remember to activate the venv first.

### Manual setup (if you prefer not to use the scripts)

```bash
cd resume_screening_system
python3.12 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## 7. Requirements

See `requirements.txt`: `fastapi`, `uvicorn`, `scikit-learn`, `numpy`, `pydantic`, `python-multipart`, `pytest`, `httpx`.

## 8. Input Format

- Job descriptions: `.txt` files under `data/job_descriptions/`.
- Resumes: `.txt` files under `data/resumes/`.
- The system references files **by filename**, e.g. `data_scientist.txt` and `candidate_01.txt` — not by uploading raw content — which keeps the API simple and mirrors how a batch-screening tool would run against a folder of resumes.
- PDF/DOCX are **not implemented** but the code is architected for it — see [Section 20](#optional-pdfdocx-extension).

## 9. NLP Pipeline

Implemented in `src/preprocessing/text_cleaner.py`:

1. **Protect special tokens** — technology names like `C++`, `C#`, `.NET`, `Node.js`, `scikit-learn`, `Power BI` are swapped for placeholders *before* cleaning.
2. **Lowercase** the text.
3. **Remove punctuation** (except the placeholders' underscores).
4. **Normalize whitespace** to single spaces.
5. **Tokenize** on whitespace.
6. **Remove stopwords** (a local, dependency-free stopword list).
7. **Optional lemmatization** — lightweight suffix stripping, skipped for short tokens and known acronyms (`sql`, `aws`, `nlp`, ...) so it can't mangle them.
8. **Restore special tokens** — placeholders are swapped back for the real technology name.

**Design decision — why we don't blindly strip all punctuation:** doing so would turn `C++` into `C`, `.NET` into `NET`, and `scikit-learn` into `scikit learn`, destroying exactly the tokens the skill extractor depends on. Protecting them first and restoring them after keeps the rest of the pipeline simple while preserving technical accuracy.

## 10. TF-IDF

`TfidfVectorizer` from scikit-learn converts the JD and resume into TF-IDF vectors, fit jointly on the 2-document corpus so IDF weights are shared and comparable. See `docs/INTERVIEW_GUIDE.md` for the full TF/IDF formulas and a worked numeric example.

## 11. Cosine Similarity

`cosine_similarity()` measures the angle between the JD vector and the resume vector — a value in `[0, 1]` where `1` means the two documents use identical word-frequency patterns and `0` means no shared vocabulary at all. It is length-independent, which matters because resumes and JDs vary a lot in length.

## 12. Skill Extraction

`src/extraction/skill_extractor.py` checks a configurable dictionary (`TECHNICAL_SKILLS` in `config.py`) against the cleaned text of both documents using substring matching on space-padded tokens. This is deliberately a **dictionary lookup**, not a trained NER model — every match is 100% reproducible and traceable to a literal entry in the config file.

## 13. Experience Extraction

`src/matching/scoring.py::extract_experience_match` uses a regular expression (`\d+(?:\.\d+)?\s*\+?...year`) to pull the first "N years" style mention out of the JD (required) and resume (candidate). This is intentionally rule-based rather than ML-based, so the number it extracts can always be pointed to in the source text.

## 14. ATS Scoring Formula

```
ATS Score = (text_similarity_score   × 0.50)
          + (skill_match_score        × 0.30)
          + (experience_match_score   × 0.10)
          + (keyword_match_score      × 0.10)
```

All four components are pre-normalized to a 0–100 scale before weighting. Weights live in `config.SCORING_WEIGHTS` and are validated at import time to sum to `1.0`. The score is rounded to two decimal places.

**This is an ATS-style *screening* score, not a prediction of hiring probability.** Recommendation labels (`Strong Match` ≥ 80, `Moderate Match` 60–79, `Low Match` < 60) are **application-defined categories**, configurable in `config.SCORE_THRESHOLDS` — not a hiring decision.

## 15. API Endpoints

| Method | Path            | Description                                      |
|--------|-----------------|---------------------------------------------------|
| GET    | `/`             | API info                                          |
| GET    | `/health`       | Health check                                      |
| GET    | `/jobs`         | List available JD files                           |
| GET    | `/resumes`      | List available resume files                       |
| POST   | `/reload`       | Re-scan `data/` for new files                     |
| POST   | `/screen`       | Screen one resume against one JD                  |
| POST   | `/screen/batch` | Screen multiple resumes against one JD, ranked    |

Interactive Swagger docs: `http://127.0.0.1:8000/docs`

## 16. Sample Request

```bash
./run.sh   # or: source venv/bin/activate && uvicorn src.main:app --reload

curl -X POST "http://127.0.0.1:8000/screen?job_description_file=data_scientist.txt&resume_file=candidate_01.txt"
```

Batch:

```bash
curl -X POST "http://127.0.0.1:8000/screen/batch?job_description_file=data_scientist.txt" \
     -H "Content-Type: application/json" \
     -d '["candidate_01.txt", "candidate_02.txt", "candidate_03.txt"]'
```

## 17. Sample Response

```json
{
  "candidate": "candidate_01",
  "ats_score": 78.04,
  "text_similarity_score": 56.54,
  "skill_match_score": 100.0,
  "experience_match_score": 100.0,
  "keyword_match_score": 97.67,
  "matched_skills": ["python", "sql", "machine learning", "nlp", "..."],
  "missing_skills": [],
  "matched_keywords": ["python", "sql", "data", "..."],
  "missing_keywords": ["visualization"],
  "required_experience": 3.0,
  "candidate_experience": 3.5,
  "recommendation": "Moderate Match"
}
```

*(This is a real output from running the sample data in this repo — note that even a strong candidate with 100% skill match can land in "Moderate Match" because raw TF-IDF text similarity is only 56.54%. See Limitations below — this is a genuine, instructive example of TF-IDF's lexical-only nature, not a demo cherry-picked to look perfect.)*

## 18. Testing

```bash
source venv/bin/activate        # Windows: venv\Scripts\activate
PYTHONPATH=. pytest tests/ -v
```

38 tests covering text cleaning, tokenization, special-token preservation, skill extraction, TF-IDF/cosine similarity (identical/partial/no overlap), experience matching, keyword matching, the final weighted ATS score and its bounds/recommendation thresholds, and full API integration tests (health, listing, screen, batch, error handling).

## 19. Limitations

- **TF-IDF is lexical, not semantic.** It compares word overlap, not meaning. "ML" and "machine learning" are unrelated to it unless the exact tokens match. This is why a genuinely qualified candidate (100% skill match) can still show only ~56% text similarity if their resume phrasing doesn't closely mirror the JD's wording.
- **No synonym recognition.** "Postgres" vs "PostgreSQL", "Azure ML" vs "Azure", etc. are treated as different tokens.
- **Resume formatting affects extraction.** Tables, headers, or unusual layouts in a real-world PDF/DOCX resume can break plain-text extraction (not exercised here since input is TXT-only).
- **Skill dictionary requires maintenance.** Any skill not listed in `config.TECHNICAL_SKILLS` will never be detected.
- **Rule-based experience extraction is simple.** It extracts the *first* "N years" mention; resumes with experience details scattered non-adjacently to "years" may not be parsed correctly.
- **The ATS score is not a hiring-probability model.** It has not been trained or validated against real hiring outcomes; it is a transparent, rule-based screening heuristic.
- **Bias risk.** The skill dictionary, keyword filters and scoring weights are human-authored and can encode bias (e.g. favoring certain tool names, certain phrasing styles, or certain resume formats) — they should be reviewed periodically.

## 20. Future Enhancements {#optional-pdfdocx-extension}

- Replace/augment TF-IDF with **Sentence Transformers / BERT / SBERT** embeddings for true semantic similarity.
- Add **Named Entity Recognition (NER)** for more flexible skill/experience extraction.
- **LLM-based resume parsing** for unstructured, free-form resumes.
- **Vector databases + semantic search** for large-scale candidate pools.
- **RAG** to let a recruiter ask natural-language questions about a candidate pool.
- **PDF/DOCX parsing** via `pypdf`/`python-docx`, plugged into the existing `DocumentReader` interface (`src/extraction/document_reader.py`) with zero changes needed elsewhere in the pipeline.
- A **Streamlit or React** frontend on top of the existing FastAPI backend.
- **Docker** containerization and cloud deployment (AWS/GCP/Azure).

---

## How to Explain This Project in an Interview

### 2-Minute Explanation

"I built an AI-powered resume screening system that mimics how an ATS ranks candidates against a job description — end to end, from raw text to a ranked shortlist, served through a FastAPI backend.

The core idea is that the score has to be **explainable**, not a black box. So instead of one similarity number, I combine four transparent signals: TF-IDF cosine similarity for lexical text overlap, a dictionary-based skill match, a rule-based experience-years match, and a keyword-coverage check — combined with configurable weights into a final 0–100 ATS score with a matched/missing breakdown for each candidate.

I was intentional about a few engineering decisions: I protect technology tokens like `C++`, `.NET` and `scikit-learn` before running punctuation-stripping so I don't destroy meaningful names; I validate that the scoring weights sum to 1.0 at import time; and I architected file reading behind a `DocumentReader` interface so PDF/DOCX support can be added later without touching the scoring logic.

It's fully unit- and API-tested with pytest, and the README is explicit that this is a *screening heuristic*, not a hiring-probability model — TF-IDF is lexical, not semantic, and I show that limitation directly in the sample output, where a 100%-skill-match candidate still lands at 'Moderate Match' because their resume phrasing doesn't closely mirror the JD's wording."

### 10 Likely Interviewer Questions with Strong Answers

**1. Why TF-IDF instead of just counting keyword matches?**
TF-IDF weighs a word by how frequent it is in *this* document, but down-weights it if it's common across *all* documents. A pure keyword count would treat "experience" (in nearly every JD) the same as "PySpark" (rare, distinctive). TF-IDF makes the distinctive, JD-specific terms matter more.

**2. Why cosine similarity and not Euclidean distance?**
Euclidean distance is sensitive to document *length* — a longer resume would look "far" from a short JD even if it used exactly the same proportion of relevant words. Cosine similarity measures the *angle* between vectors, which captures word-usage *pattern* independent of length — the right property for comparing a short JD to a long resume.

**3. Is TF-IDF "semantic understanding"?**
No — that's an important distinction I'm careful to call out. TF-IDF is purely lexical: it only sees whether the *same tokens* appear in both documents. It has no concept of meaning, so "ML" and "machine learning" are unrelated to it. For true semantic similarity you'd want embeddings from a Sentence Transformer or BERT-family model.

**4. Why didn't you train a supervised ML model to predict fit?**
Two reasons: I didn't have a labeled dataset of resumes with ground-truth hiring outcomes (and using proxy labels would bake in whatever bias produced those historical outcomes), and a rule-based, weighted-component score is far more explainable to a candidate or recruiter than a trained model's opaque prediction. Explainability was a first-class requirement here.

**5. How would you extend this to real PDF/DOCX resumes?**
The file-reading layer is behind a `DocumentReader` abstract interface. I'd add a `PdfDocumentReader` (using `pypdf`) and `DocxDocumentReader` (using `python-docx`), register them in the extension-to-reader mapping, and nothing else in the pipeline — skill extraction, TF-IDF, scoring — would need to change.

**6. How do you keep the scoring weights from becoming inconsistent?**
`SCORING_WEIGHTS` lives in one config file and is validated at import time to sum to 1.0; if someone edits it incorrectly the app fails fast at startup rather than silently producing a miscalibrated score.

**7. How does your system handle a JD or resume with no detectable skills?**
Skill match defaults to 100% when the JD lists zero skills, since there's nothing to fail against — that's a deliberate edge-case decision to avoid dividing by zero and to avoid unfairly penalizing a candidate for a JD that just wasn't skill-tagged well.

**8. Why protect tokens like `.NET` and `C++` before removing punctuation?**
A blind "strip all punctuation" step would turn `.NET` into `NET` and `C++` into `C`, silently corrupting exactly the technology names the skill extractor is trying to detect. I swap them for placeholder tokens before cleaning and restore them afterward.

**9. What's the biggest limitation of this system, and how would you fix it?**
The reliance on lexical (not semantic) similarity — a candidate who describes the same experience in different words scores lower than they should. I'd address this by adding a semantic similarity component using sentence embeddings, and blending it with the existing TF-IDF score rather than replacing it outright (so the system stays explainable while getting more accurate).

**10. How did you test this, and what would you add for production?**
38 pytest tests cover unit-level behavior (cleaning, tokenization, special-token protection, TF-IDF edge cases like identical/disjoint documents, experience/keyword matching, ATS score bounds and thresholds) and API-level integration tests via FastAPI's TestClient. For production I'd add: load/performance testing for large resume batches, input-size limits, authentication on the API, and a bias audit of the skill dictionary and scoring weights against a diverse resume sample.
