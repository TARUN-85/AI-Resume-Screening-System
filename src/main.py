"""
FastAPI application entry point for the AI Resume Screening System.

Run with:
    uvicorn src.main:app --reload

Then open http://127.0.0.1:8000/docs for interactive Swagger/OpenAPI docs.
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from src.config import JOB_DESCRIPTIONS_DIR, RESUMES_DIR
from src.schemas.response_models import (
    BatchScreenResponse,
    HealthResponse,
    JobDescriptionListResponse,
    ReloadResponse,
    ResumeListResponse,
    ScreenResult,
)
from src.services.screening_service import (
    ScreeningError,
    list_job_descriptions,
    list_resumes,
    screen_batch,
    screen_resume,
)
from src.utils.logger import get_logger

logger = get_logger(__name__)

app = FastAPI(
    title="AI Resume Screening System",
    description=(
        "An explainable, TF-IDF + rule-based ATS screening API. "
        "Scores are reproducible and mathematically explainable -- "
        "NOT randomly generated, and NOT a hiring-probability prediction."
    ),
    version="1.0.0",
)


@app.exception_handler(ScreeningError)
async def screening_error_handler(request: Request, exc: ScreeningError):
    logger.error("ScreeningError on %s: %s", request.url.path, exc)
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.get("/", tags=["General"])
async def root():
    return {
        "message": "AI Resume Screening System API",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health", response_model=HealthResponse, tags=["General"])
async def health():
    return HealthResponse(status="ok", message="Service is healthy.")


@app.get("/jobs", response_model=JobDescriptionListResponse, tags=["Data"])
async def get_jobs():
    return JobDescriptionListResponse(job_descriptions=list_job_descriptions())


@app.get("/resumes", response_model=ResumeListResponse, tags=["Data"])
async def get_resumes():
    return ResumeListResponse(resumes=list_resumes())


@app.post("/reload", response_model=ReloadResponse, tags=["Data"])
async def reload_data():
    """
    Re-scan the data/ directories. Useful after adding new JD/resume
    files to disk without restarting the server.
    """
    jobs = list_job_descriptions()
    resumes = list_resumes()
    return ReloadResponse(
        status="reloaded",
        job_descriptions_found=len(jobs),
        resumes_found=len(resumes),
    )


@app.post("/screen", response_model=ScreenResult, tags=["Screening"])
async def screen(job_description_file: str, resume_file: str):
    """
    Screen ONE resume against ONE job description.

    - **job_description_file**: filename inside data/job_descriptions/ (e.g. "data_scientist.txt")
    - **resume_file**: filename inside data/resumes/ (e.g. "candidate_01.txt")
    """
    if not job_description_file or not resume_file:
        raise HTTPException(status_code=400, detail="job_description_file and resume_file are required.")

    try:
        return screen_resume(job_description_file, resume_file)
    except ScreeningError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/screen/batch", response_model=BatchScreenResponse, tags=["Screening"])
async def screen_batch_endpoint(job_description_file: str, resume_files: list[str]):
    """
    Screen MULTIPLE resumes against ONE job description, ranked
    descending by ATS score.

    - **job_description_file**: filename inside data/job_descriptions/
    - **resume_files**: list of filenames inside data/resumes/
    """
    if not job_description_file:
        raise HTTPException(status_code=400, detail="job_description_file is required.")
    if not resume_files:
        raise HTTPException(status_code=400, detail="resume_files must contain at least one filename.")

    result = screen_batch(job_description_file, resume_files)

    if not result["detailed_results"] and result["errors"]:
        raise HTTPException(
            status_code=422,
            detail=f"All resumes failed to screen: {result['errors']}",
        )

    return BatchScreenResponse(
        job_description=result["job_description"],
        ranked_summary=result["ranked_summary"],
        detailed_results=result["detailed_results"],
    )


@app.on_event("startup")
async def on_startup():
    JOB_DESCRIPTIONS_DIR.mkdir(parents=True, exist_ok=True)
    RESUMES_DIR.mkdir(parents=True, exist_ok=True)
    logger.info(
        "Startup complete. %d job descriptions, %d resumes found.",
        len(list_job_descriptions()),
        len(list_resumes()),
    )
