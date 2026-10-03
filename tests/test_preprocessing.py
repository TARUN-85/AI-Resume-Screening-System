"""Unit tests for text preprocessing (text cleaning, tokenization, skill extraction)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.extraction.skill_extractor import compare_skills, extract_skills
from src.preprocessing.text_cleaner import (
    clean_text,
    lowercase,
    normalize_whitespace,
    remove_stopwords,
    tokenize,
)


def test_lowercase():
    assert lowercase("Python DEVELOPER") == "python developer"


def test_normalize_whitespace():
    assert normalize_whitespace("Python   is   great") == "Python is great"


def test_tokenize():
    assert tokenize("python is great") == ["python", "is", "great"]


def test_remove_stopwords():
    tokens = ["python", "is", "a", "great", "language"]
    result = remove_stopwords(tokens)
    assert "is" not in result
    assert "a" not in result
    assert "python" in result
    assert "great" in result


def test_clean_text_basic():
    result = clean_text("I have 3 years of Python and SQL experience!")
    assert "python" in result.tokens
    assert "sql" in result.tokens
    assert "!" not in result.cleaned_text


def test_clean_text_preserves_special_tech_tokens():
    result = clean_text("Experience with C++, C#, .NET and Node.js required.")
    assert "c++" in result.tokens
    assert "c#" in result.tokens
    assert ".net" in result.tokens
    assert "node.js" in result.tokens


def test_clean_text_preserves_scikit_learn_and_power_bi():
    result = clean_text("Experience with scikit-learn and Power BI required.")
    assert "scikit-learn" in result.tokens
    assert "power bi" in result.tokens


def test_clean_text_empty_input():
    result = clean_text("")
    assert result.tokens == []
    assert result.cleaned_text == ""


def test_extract_skills_finds_known_skills():
    cleaned = clean_text("I have experience with python, sql and machine learning")
    result = extract_skills(cleaned.cleaned_text)
    assert "python" in result.found_skills
    assert "sql" in result.found_skills
    assert "machine learning" in result.found_skills


def test_extract_skills_empty_text_returns_empty_set():
    result = extract_skills("")
    assert result.found_skills == set()


def test_compare_skills_matched_and_missing():
    jd_skills = {"python", "sql", "aws"}
    resume_skills = {"python", "sql"}
    result = compare_skills(jd_skills, resume_skills)
    assert result["matched_skills"] == ["python", "sql"]
    assert result["missing_skills"] == ["aws"]
    assert result["skill_match_percentage"] == round(2 / 3 * 100, 2)


def test_compare_skills_no_jd_skills_returns_full_percentage():
    result = compare_skills(set(), {"python"})
    assert result["skill_match_percentage"] == 100.0
