# tests/test_api_routes.py
import io
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from api.main import app

client = TestClient(app)


def test_post_jobs_requires_file_or_url():
    resp = client.post("/api/jobs")
    # FastAPI validation (no fields at all) — 422 on older httpx, 400 on newer
    assert resp.status_code in (400, 422)


def test_post_jobs_rejects_empty_body():
    resp = client.post("/api/jobs", data={})
    assert resp.status_code == 400


def test_post_jobs_with_url_returns_job_id():
    with patch("api.worker.run_job"):  # don't actually run the pipeline
        resp = client.post("/api/jobs", data={"youtube_url": "https://youtube.com/watch?v=test"})
    assert resp.status_code == 200
    body = resp.json()
    assert "job_id" in body
    assert body["status"] == "queued"


def test_get_status_not_found():
    resp = client.get("/api/jobs/doesnotexist/status")
    assert resp.status_code == 404


def test_get_status_returns_queued_for_new_job():
    with patch("api.worker.run_job"):
        create_resp = client.post("/api/jobs", data={"youtube_url": "https://youtube.com/watch?v=test"})
    job_id = create_resp.json()["job_id"]
    status_resp = client.get(f"/api/jobs/{job_id}/status")
    assert status_resp.status_code == 200
    assert status_resp.json()["status"] in ("queued", "running")


def test_get_results_returns_409_when_not_done():
    with patch("api.worker.run_job"):
        create_resp = client.post("/api/jobs", data={"youtube_url": "https://youtube.com/watch?v=test"})
    job_id = create_resp.json()["job_id"]
    resp = client.get(f"/api/jobs/{job_id}/results")
    assert resp.status_code == 409


def test_post_jobs_with_file_returns_job_id():
    fake_audio = io.BytesIO(b"RIFF" + b"\x00" * 100)
    with patch("api.worker.run_job"):
        resp = client.post(
            "/api/jobs",
            files={"file": ("test.wav", fake_audio, "audio/wav")},
        )
    assert resp.status_code == 200
    assert "job_id" in resp.json()
