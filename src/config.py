"""
Central configuration for the AI Resume Screening System.

Keeping configuration in one place (instead of scattering magic numbers
and paths across the codebase) makes the scoring logic easy to tune,
audit and explain in an interview: every weight or threshold that
affects the final score can be found here.
"""

from pathlib import Path

# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------
# BASE_DIR resolves to the project root regardless of where the app is
# launched from -- this avoids hardcoded absolute paths.
BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data"
JOB_DESCRIPTIONS_DIR = DATA_DIR / "job_descriptions"
RESUMES_DIR = DATA_DIR / "resumes"

# --------------------------------------------------------------------------
# Supported file types (TXT now; the DocumentReader interface in
# extraction/ makes it straightforward to add PDF/DOCX readers later
# without changing any downstream code).
# --------------------------------------------------------------------------
SUPPORTED_EXTENSIONS = {".txt"}

# --------------------------------------------------------------------------
# Skill dictionary
# --------------------------------------------------------------------------
# A curated, lower-cased set of technical skills the system looks for in
# both the JD and the resume. This is intentionally simple and
# rule-based (not a trained NER model) so that every match is
# deterministic and explainable -- a core requirement for an ATS-style
# scoring system used in interview discussions.
TECHNICAL_SKILLS = {
    "python", "sql", "mysql", "postgresql", "pandas", "numpy",
    "scikit-learn", "sklearn", "tensorflow", "pytorch", "keras",
    "machine learning", "deep learning", "nlp",
    "fastapi", "flask", "docker", "kubernetes",
    "aws", "azure", "gcp",
    "spark", "pyspark", "power bi", "tableau", "excel",
    "git", "jenkins", "ci/cd", "airflow",
    "c++", "c#", ".net", "node.js", "java", "spring boot",
    "rest api", "rest apis", "statistics", "a/b testing",
}

# Words that are too generic to count as meaningful "keywords" when
# extracting keywords from a JD (they would otherwise pollute the
# keyword-match calculation with near-universal terms).
GENERIC_STOP_KEYWORDS = {
    "good", "strong", "candidate", "experience", "knowledge",
    "working", "years", "year", "team", "ability", "skills",
    "role", "join", "looking", "plus", "related", "field",
    "job", "title", "summary", "responsibilities", "requirements",
    "nice", "ideal", "build", "building", "collaborate",
    "collaborating", "communicate", "communication", "productionize",
    "proficiency", "validate", "deploy", "deploying", "perform",
    "performing", "extract", "analyze", "analyzing", "analysis",
    "insights", "actionable", "findings", "stakeholders",
    "non", "technical", "problem", "solving", "degree", "bachelor",
    "familiarity", "platforms", "cloud", "containerization",
    "consuming", "big", "large", "small", "using", "based",
    "solutions", "solution", "business", "work", "help",
}

# --------------------------------------------------------------------------
# ATS scoring weights
# --------------------------------------------------------------------------
# These weights MUST sum to 1.0. They are read once at startup and
# validated in scoring.py.
SCORING_WEIGHTS = {
    "text_similarity": 0.50,
    "skill_match": 0.30,
    "experience_match": 0.10,
    "keyword_match": 0.10,
}

# --------------------------------------------------------------------------
# Recommendation thresholds
# --------------------------------------------------------------------------
# Application-defined categories only -- NOT a hiring decision.
SCORE_THRESHOLDS = {
    "strong_match": 80.0,   # ats_score >= 80        -> "Strong Match"
    "moderate_match": 60.0,  # 60 <= ats_score < 80   -> "Moderate Match"
    # ats_score < 60                                   -> "Low Match"
}

# --------------------------------------------------------------------------
# Experience extraction
# --------------------------------------------------------------------------
# Default assumed required experience when the JD does not state one
# explicitly, and the experience score awarded when a resume states no
# experience at all. Kept configurable rather than hardcoded inline.
DEFAULT_REQUIRED_EXPERIENCE_YEARS = 0.0
EXPERIENCE_SCORE_WHEN_UNSTATED_REQUIREMENT = 100.0

# --------------------------------------------------------------------------
# Logging
# --------------------------------------------------------------------------
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
