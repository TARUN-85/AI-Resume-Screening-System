"""
Rule-based skill extraction.

Skills are matched against a configurable dictionary (config.TECHNICAL_SKILLS)
using simple substring/phrase matching on the *cleaned* text. This is a
deliberate design choice: a trained Named Entity Recognition (NER) model
could extract skills more flexibly, but it would also be a black box that
is much harder to explain and reproduce in an interview setting. A
dictionary lookup is 100% deterministic and auditable -- every match can
be traced back to an exact entry in TECHNICAL_SKILLS.
"""

from dataclasses import dataclass

from src.config import TECHNICAL_SKILLS
from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class SkillExtractionResult:
    found_skills: set[str]


def extract_skills(cleaned_text: str) -> SkillExtractionResult:
    """
    Find which skills from TECHNICAL_SKILLS appear in the given cleaned
    text. Multi-word skills (e.g. "machine learning", "power bi") are
    matched as substrings of the space-joined token string, which is
    correct because clean_text() normalizes whitespace to single spaces.
    """
    if not cleaned_text:
        return SkillExtractionResult(found_skills=set())

    padded_text = f" {cleaned_text} "
    found = set()
    for skill in TECHNICAL_SKILLS:
        needle = f" {skill} "
        if needle in padded_text:
            found.add(skill)

    logger.info("Extracted %d skills", len(found))
    return SkillExtractionResult(found_skills=found)


def compare_skills(jd_skills: set[str], resume_skills: set[str]) -> dict:
    """
    Compare JD skills against resume skills.

    Returns matched skills, missing skills, and skill match percentage.
    skill_match_percentage is 100.0 when the JD lists zero skills
    (nothing to match against), rather than raising a division error.
    """
    matched = jd_skills & resume_skills
    missing = jd_skills - resume_skills

    if not jd_skills:
        match_pct = 100.0
    else:
        match_pct = round((len(matched) / len(jd_skills)) * 100, 2)

    return {
        "jd_skills": sorted(jd_skills),
        "resume_skills": sorted(resume_skills),
        "matched_skills": sorted(matched),
        "missing_skills": sorted(missing),
        "skill_match_percentage": match_pct,
    }
