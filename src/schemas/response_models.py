"""
Pydantic response/request models for the FastAPI layer.

Using Pydantic models (instead of returning raw dicts) gives us automatic
request/response validation, auto-generated OpenAPI/Swagger docs, and
clear, typed contracts between the API and its clients.
"""

from pydantic import BaseModel, Field


class ScreenResult(BaseModel):
    candidate: str
    ats_score: float
    text_similarity_score: float
    skill_match_score: float
    experience_match_score: float
    keyword_match_score: float
    matched_skills: list[str]
    missing_skills: list[str]
    matched_keywords: list[str]
    missing_keywords: list[str]
    required_experience: float
    candidate_experience: float
    recommendation: str = Field(
        ..., description="Application-defined category, NOT a hiring decision."
    )


class BatchSummaryItem(BaseModel):
    candidate: str
    ats_score: float
    recommendation: str


class BatchScreenResponse(BaseModel):
    job_description: str
    ranked_summary: list[BatchSummaryItem]
    detailed_results: list[ScreenResult]


class ErrorResponse(BaseModel):
    detail: str


class HealthResponse(BaseModel):
    status: str
    message: str


class JobDescriptionListResponse(BaseModel):
    job_descriptions: list[str]


class ResumeListResponse(BaseModel):
    resumes: list[str]


class ReloadResponse(BaseModel):
    status: str
    job_descriptions_found: int
    resumes_found: int
