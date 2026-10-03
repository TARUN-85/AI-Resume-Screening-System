"""
Unit tests for TF-IDF matching, cosine similarity, experience matching,
keyword matching, and the final ATS scoring engine.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.matching.scoring import (
    ScoringConfigError,
    compute_ats_score,
    compute_keyword_match,
    extract_experience_match,
)
from src.matching.tfidf_matcher import TfidfMatchError, compute_text_similarity


# --------------------------------------------------------------------------
# TF-IDF / cosine similarity
# --------------------------------------------------------------------------
def test_identical_documents_have_similarity_one():
    text = "python sql machine learning aws docker"
    result = compute_text_similarity(text, text)
    assert result.similarity_score == pytest.approx(1.0, abs=1e-6)
    assert result.similarity_percentage == 100.0


def test_completely_different_documents_have_low_similarity():
    jd = "python sql machine learning aws docker fastapi"
    resume = "gardening cooking painting hiking travel photography"
    result = compute_text_similarity(jd, resume)
    assert result.similarity_score < 0.2


def test_partial_overlap_gives_intermediate_similarity():
    jd = "python sql machine learning"
    resume = "python sql web development java"
    result = compute_text_similarity(jd, resume)
    assert 0.0 < result.similarity_score < 1.0


def test_empty_text_raises_tfidf_match_error():
    with pytest.raises(TfidfMatchError):
        compute_text_similarity("", "python sql")
    with pytest.raises(TfidfMatchError):
        compute_text_similarity("python sql", "   ")


# --------------------------------------------------------------------------
# Experience matching
# --------------------------------------------------------------------------
def test_experience_meets_requirement_scores_100():
    result = extract_experience_match(
        "Looking for 3+ years of experience", "I have 3.5 years of experience"
    )
    assert result.required_experience_years == 3.0
    assert result.candidate_experience_years == 3.5
    assert result.experience_match_score == 100.0


def test_experience_below_requirement_scores_proportionally():
    result = extract_experience_match(
        "Looking for 4 years of experience", "I have 2 years of experience"
    )
    assert result.experience_match_score == pytest.approx(50.0, abs=0.01)


def test_experience_unstated_requirement_scores_full():
    result = extract_experience_match("Great team culture.", "I have 1 year of experience")
    assert result.experience_match_score == 100.0


def test_experience_unstated_candidate_defaults_to_zero():
    result = extract_experience_match("Looking for 2+ years of experience", "Skilled developer.")
    assert result.candidate_experience_years == 0.0
    assert result.experience_match_score == 0.0


# --------------------------------------------------------------------------
# Keyword matching
# --------------------------------------------------------------------------
def test_keyword_match_basic():
    jd_tokens = ["python", "sql", "machine", "learning", "aws"]
    resume_tokens = ["python", "sql", "machine", "learning"]
    result = compute_keyword_match(jd_tokens, resume_tokens)
    assert "aws" in result.missing_keywords
    assert "python" in result.matched_keywords


def test_keyword_match_ignores_generic_words():
    jd_tokens = ["good", "candidate", "python", "experience"]
    resume_tokens = ["python"]
    result = compute_keyword_match(jd_tokens, resume_tokens)
    assert "good" not in result.jd_keywords
    assert "candidate" not in result.jd_keywords
    assert "python" in result.jd_keywords


def test_keyword_match_empty_jd_keywords_returns_100():
    result = compute_keyword_match(["good", "experience"], ["python"])
    assert result.keyword_match_percentage == 100.0


# --------------------------------------------------------------------------
# Final ATS score
# --------------------------------------------------------------------------
def test_compute_ats_score_weighted_combination():
    breakdown = compute_ats_score(
        text_similarity_percentage=80.0,
        skill_match_percentage=100.0,
        experience_match_score=100.0,
        keyword_match_percentage=50.0,
    )
    expected = 80.0 * 0.50 + 100.0 * 0.30 + 100.0 * 0.10 + 50.0 * 0.10
    assert breakdown.ats_score == round(expected, 2)


def test_compute_ats_score_strong_match_recommendation():
    breakdown = compute_ats_score(90.0, 90.0, 100.0, 90.0)
    assert breakdown.recommendation == "Strong Match"


def test_compute_ats_score_moderate_match_recommendation():
    breakdown = compute_ats_score(65.0, 65.0, 65.0, 65.0)
    assert breakdown.recommendation == "Moderate Match"


def test_compute_ats_score_low_match_recommendation():
    breakdown = compute_ats_score(10.0, 10.0, 10.0, 10.0)
    assert breakdown.recommendation == "Low Match"


def test_compute_ats_score_is_bounded_between_0_and_100():
    breakdown = compute_ats_score(100.0, 100.0, 100.0, 100.0)
    assert breakdown.ats_score <= 100.0
    breakdown = compute_ats_score(0.0, 0.0, 0.0, 0.0)
    assert breakdown.ats_score >= 0.0
