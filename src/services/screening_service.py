"""
Screening service: orchestrates the full pipeline for one JD-vs-resume
comparison, and for batch (one JD vs many resumes) screening.

Pipeline:
    Input (file paths)
      -> File Reader (extraction.document_reader)
      -> Text Preprocessor (preprocessing.text_cleaner)
      -> Skill Extractor (extraction.skill_extractor)
      -> TF-IDF + Cosine Similarity (matching.tfidf_matcher)
      -> Experience & Keyword Matching (matching.scoring)
      -> ATS Scoring Engine (matching.scoring)
      -> Response Schema (schemas.response_models)
"""

from pathlib import Path

from src.config import JOB_DESCRIPTIONS_DIR, RESUMES_DIR
from src.extraction.document_reader import DocumentReadError, read_document
from src.extraction.skill_extractor import compare_skills, extract_skills
from src.matching.scoring import (
    compute_ats_score,
    compute_keyword_match,
    extract_experience_match,
)
from src.matching.tfidf_matcher import TfidfMatchError, compute_text_similarity
from src.preprocessing.text_cleaner import clean_text
from src.schemas.response_models import BatchSummaryItem, ScreenResult
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ScreeningError(Exception):
    """Raised for any expected/handled failure during screening."""


def _resolve_path(directory: Path, filename: str) -> Path:
    """
    Resolve a filename against an allowed base directory and guard
    against path traversal (e.g. '../../etc/passwd').
    """
    candidate = (directory / filename).resolve()
    if directory.resolve() not in candidate.parents and candidate != directory.resolve():
        raise ScreeningError(f"Invalid file path: {filename}")
    return candidate


def screen_resume(job_description_file: str, resume_file: str) -> ScreenResult:
    """
    Run the full screening pipeline for a single JD/resume pair.
    Filenames are resolved relative to data/job_descriptions and
    data/resumes respectively.
    """
    jd_path = _resolve_path(JOB_DESCRIPTIONS_DIR, job_description_file)
    resume_path = _resolve_path(RESUMES_DIR, resume_file)

    logger.info("Screening resume '%s' against JD '%s'", resume_path.name, jd_path.name)

    try:
        jd_raw = read_document(jd_path)
        resume_raw = read_document(resume_path)
    except DocumentReadError as exc:
        raise ScreeningError(str(exc)) from exc

    jd_cleaned = clean_text(jd_raw)
    resume_cleaned = clean_text(resume_raw)

    if not jd_cleaned.tokens:
        raise ScreeningError("Job description contains no usable text after cleaning.")
    if not resume_cleaned.tokens:
        raise ScreeningError("Resume contains no usable text after cleaning.")

    # --- Text similarity (TF-IDF + cosine similarity) ---
    try:
        similarity = compute_text_similarity(jd_cleaned.cleaned_text, resume_cleaned.cleaned_text)
    except TfidfMatchError as exc:
        raise ScreeningError(str(exc)) from exc

    # --- Skill matching ---
    jd_skills = extract_skills(jd_cleaned.cleaned_text).found_skills
    resume_skills = extract_skills(resume_cleaned.cleaned_text).found_skills
    skill_result = compare_skills(jd_skills, resume_skills)

    if not jd_skills:
        logger.info("No skills detected in JD '%s'; skill_match defaults to 100.", jd_path.name)

    # --- Experience matching ---
    experience_result = extract_experience_match(jd_raw, resume_raw)

    # --- Keyword matching ---
    keyword_result = compute_keyword_match(jd_cleaned.tokens, resume_cleaned.tokens)

    # --- Final ATS score ---
    breakdown = compute_ats_score(
        text_similarity_percentage=similarity.similarity_percentage,
        skill_match_percentage=skill_result["skill_match_percentage"],
        experience_match_score=experience_result.experience_match_score,
        keyword_match_percentage=keyword_result.keyword_match_percentage,
    )

    return ScreenResult(
        candidate=resume_path.stem,
        ats_score=breakdown.ats_score,
        text_similarity_score=breakdown.text_similarity_score,
        skill_match_score=breakdown.skill_match_score,
        experience_match_score=breakdown.experience_match_score,
        keyword_match_score=breakdown.keyword_match_score,
        matched_skills=skill_result["matched_skills"],
        missing_skills=skill_result["missing_skills"],
        matched_keywords=keyword_result.matched_keywords,
        missing_keywords=keyword_result.missing_keywords,
        required_experience=experience_result.required_experience_years,
        candidate_experience=experience_result.candidate_experience_years,
        recommendation=breakdown.recommendation,
    )


def screen_batch(job_description_file: str, resume_files: list[str]) -> dict:
    """
    Screen multiple resumes against a single JD, returning both a
    ranked summary (sorted descending by ats_score) and full detailed
    results for every candidate. A failure on one resume is recorded as
    an error for that candidate without aborting the whole batch.
    """
    detailed_results: list[ScreenResult] = []
    errors: list[dict] = []

    for resume_file in resume_files:
        try:
            result = screen_resume(job_description_file, resume_file)
            detailed_results.append(result)
        except ScreeningError as exc:
            logger.error("Failed to screen '%s': %s", resume_file, exc)
            errors.append({"candidate": resume_file, "error": str(exc)})

    detailed_results.sort(key=lambda r: r.ats_score, reverse=True)
    ranked_summary = [
        BatchSummaryItem(
            candidate=r.candidate, ats_score=r.ats_score, recommendation=r.recommendation
        )
        for r in detailed_results
    ]

    return {
        "job_description": Path(job_description_file).stem,
        "ranked_summary": ranked_summary,
        "detailed_results": detailed_results,
        "errors": errors,
    }


def list_job_descriptions() -> list[str]:
    if not JOB_DESCRIPTIONS_DIR.exists():
        return []
    return sorted(p.name for p in JOB_DESCRIPTIONS_DIR.glob("*.txt"))


def list_resumes() -> list[str]:
    if not RESUMES_DIR.exists():
        return []
    return sorted(p.name for p in RESUMES_DIR.glob("*.txt"))
