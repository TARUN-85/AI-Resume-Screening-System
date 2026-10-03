"""
API-level tests using FastAPI's TestClient (backed by httpx).
Exercises the real endpoints against the actual sample data files in
data/job_descriptions and data/resumes, so these also serve as
integration tests for the whole pipeline.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    assert "message" in response.json()


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"


def test_jobs_endpoint_lists_sample_data():
    response = client.get("/jobs")
    assert response.status_code == 200
    jobs = response.json()["job_descriptions"]
    assert "data_scientist.txt" in jobs


def test_resumes_endpoint_lists_sample_data():
    response = client.get("/resumes")
    assert response.status_code == 200
    resumes = response.json()["resumes"]
    assert "candidate_01.txt" in resumes


def test_screen_endpoint_success():
    response = client.post(
        "/screen",
        params={
            "job_description_file": "data_scientist.txt",
            "resume_file": "candidate_01.txt",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["candidate"] == "candidate_01"
    assert 0.0 <= body["ats_score"] <= 100.0
    assert body["recommendation"] in {"Strong Match", "Moderate Match", "Low Match"}


def test_screen_endpoint_missing_resume_file_returns_error():
    response = client.post(
        "/screen",
        params={
            "job_description_file": "data_scientist.txt",
            "resume_file": "does_not_exist.txt",
        },
    )
    assert response.status_code == 422


def test_screen_endpoint_missing_params_returns_400_or_422():
    response = client.post("/screen", params={"job_description_file": "data_scientist.txt"})
    # FastAPI returns 422 for a missing required query parameter
    assert response.status_code in (400, 422)


def test_screen_batch_endpoint_ranks_by_score_descending():
    response = client.post(
        "/screen/batch",
        params={"job_description_file": "data_scientist.txt"},
        json=["candidate_01.txt", "candidate_02.txt", "candidate_03.txt"],
    )
    assert response.status_code == 200
    body = response.json()
    scores = [item["ats_score"] for item in body["ranked_summary"]]
    assert scores == sorted(scores, reverse=True)
    assert len(body["detailed_results"]) == 3


def test_screen_batch_endpoint_empty_resume_list_returns_400():
    response = client.post(
        "/screen/batch",
        params={"job_description_file": "data_scientist.txt"},
        json=[],
    )
    assert response.status_code == 400


def test_reload_endpoint():
    response = client.post("/reload")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "reloaded"
    assert body["job_descriptions_found"] >= 3
    assert body["resumes_found"] >= 3
