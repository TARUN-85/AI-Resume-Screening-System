"""
Scoring engine: experience extraction, keyword matching, and the final
weighted ATS score.

This module deliberately keeps experience extraction and keyword
matching RULE-BASED rather than using a trained ML model. An ATS score
that a candidate can question needs a scoring path a human can walk
through by hand -- that is the whole point of an "explainable ATS
screening score" as opposed to a black-box hiring prediction.
"""

import re
from dataclasses import dataclass

from src.config import (
    DEFAULT_REQUIRED_EXPERIENCE_YEARS,
    EXPERIENCE_SCORE_WHEN_UNSTATED_REQUIREMENT,
    GENERIC_STOP_KEYWORDS,
    SCORE_THRESHOLDS,
    SCORING_WEIGHTS,
)
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Matches patterns like "3+ years", "3.5 years", "3-5 years", "3 years"
_EXPERIENCE_PATTERN = re.compile(
    r"(\d+(?:\.\d+)?)\s*\+?\s*(?:-\s*\d+(?:\.\d+)?\s*)?year", re.IGNORECASE
)


class ScoringConfigError(Exception):
    """Raised when SCORING_WEIGHTS is misconfigured."""


def _validate_weights() -> None:
    total = round(sum(SCORING_WEIGHTS.values()), 6)
    if total != 1.0:
        raise ScoringConfigError(
            f"SCORING_WEIGHTS must sum to 1.0, got {total}. Check src/config.py."
        )


_validate_weights()


# --------------------------------------------------------------------------
# Experience extraction
# --------------------------------------------------------------------------
@dataclass
class ExperienceMatchResult:
    required_experience_years: float
    candidate_experience_years: float
    experience_match_score: float  # 0-100


def _extract_years(text: str) -> float | None:
    """
    Extract the first "N years" style mention from raw text.

    This is intentionally simple: it takes the FIRST number found before
    the word "year(s)". Resumes/JDs are expected to state experience near
    the top (e.g. in a summary line), which this heuristic targets. It
    will not correctly parse experience scattered across multiple
    unrelated sentences -- a documented limitation, not a bug.
    """
    match = _EXPERIENCE_PATTERN.search(text)
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def extract_experience_match(jd_raw_text: str, resume_raw_text: str) -> ExperienceMatchResult:
    """
    Extract required experience (from JD) and candidate experience (from
    resume), then score how well the candidate meets the requirement.

    Scoring rule:
        - If JD states no explicit experience requirement -> full score
          (nothing to fail against).
        - If candidate experience >= required -> 100.
        - Else -> proportional score = (candidate / required) * 100,
          capped at 100 and floored at 0.
    """
    required = _extract_years(jd_raw_text)
    candidate = _extract_years(resume_raw_text)

    if required is None:
        required = DEFAULT_REQUIRED_EXPERIENCE_YEARS

    if candidate is None:
        candidate = 0.0

    if required <= 0:
        score = EXPERIENCE_SCORE_WHEN_UNSTATED_REQUIREMENT
    elif candidate >= required:
        score = 100.0
    else:
        score = max(0.0, min(100.0, (candidate / required) * 100))

    score = round(score, 2)
    logger.info(
        "Experience match: required=%.1f candidate=%.1f score=%.2f",
        required, candidate, score,
    )

    return ExperienceMatchResult(
        required_experience_years=required,
        candidate_experience_years=candidate,
        experience_match_score=score,
    )


# --------------------------------------------------------------------------
# Keyword matching
# --------------------------------------------------------------------------
@dataclass
class KeywordMatchResult:
    jd_keywords: list[str]
    matched_keywords: list[str]
    missing_keywords: list[str]
    keyword_match_percentage: float


def extract_keywords_from_jd(jd_tokens: list[str], min_length: int = 3) -> set[str]:
    """
    Extract "important" keywords from the JD's cleaned tokens: anything
    that is not a generic filler word (config.GENERIC_STOP_KEYWORDS) and
    is at least `min_length` characters long.
    """
    keywords = {
        tok for tok in jd_tokens
        if tok not in GENERIC_STOP_KEYWORDS and len(tok) >= min_length
    }
    return keywords


def compute_keyword_match(jd_tokens: list[str], resume_tokens: list[str]) -> KeywordMatchResult:
    jd_keywords = extract_keywords_from_jd(jd_tokens)
    resume_token_set = set(resume_tokens)

    matched = jd_keywords & resume_token_set
    missing = jd_keywords - resume_token_set

    if not jd_keywords:
        pct = 100.0
    else:
        pct = round((len(matched) / len(jd_keywords)) * 100, 2)

    return KeywordMatchResult(
        jd_keywords=sorted(jd_keywords),
        matched_keywords=sorted(matched),
        missing_keywords=sorted(missing),
        keyword_match_percentage=pct,
    )


# --------------------------------------------------------------------------
# Final ATS score
# --------------------------------------------------------------------------
@dataclass
class ATSScoreBreakdown:
    ats_score: float
    text_similarity_score: float
    skill_match_score: float
    experience_match_score: float
    keyword_match_score: float
    recommendation: str


def compute_ats_score(
    text_similarity_percentage: float,
    skill_match_percentage: float,
    experience_match_score: float,
    keyword_match_percentage: float,
) -> ATSScoreBreakdown:
    """
    Combine the four component scores (each already normalized to 0-100)
    into the final weighted ATS score, using the weights defined in
    config.SCORING_WEIGHTS:

        ATS Score = text_similarity * 0.50
                  + skill_match      * 0.30
                  + experience_match * 0.10
                  + keyword_match    * 0.10

    This is NOT simply cosine_similarity * 100 -- text similarity is only
    one of four weighted components, which is what makes the score
    explainable rather than a single opaque number.
    """
    weights = SCORING_WEIGHTS
    ats_score = (
        text_similarity_percentage * weights["text_similarity"]
        + skill_match_percentage * weights["skill_match"]
        + experience_match_score * weights["experience_match"]
        + keyword_match_percentage * weights["keyword_match"]
    )
    ats_score = round(max(0.0, min(100.0, ats_score)), 2)

    if ats_score >= SCORE_THRESHOLDS["strong_match"]:
        recommendation = "Strong Match"
    elif ats_score >= SCORE_THRESHOLDS["moderate_match"]:
        recommendation = "Moderate Match"
    else:
        recommendation = "Low Match"

    logger.info("Final ATS score: %.2f (%s)", ats_score, recommendation)

    return ATSScoreBreakdown(
        ats_score=ats_score,
        text_similarity_score=text_similarity_percentage,
        skill_match_score=skill_match_percentage,
        experience_match_score=experience_match_score,
        keyword_match_score=keyword_match_percentage,
        recommendation=recommendation,
    )
