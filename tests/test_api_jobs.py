# tests/test_api_jobs.py
import time
from api import jobs


def test_create_job_returns_unique_ids():
    a = jobs.create_job()
    b = jobs.create_job()
    assert a.job_id != b.job_id


def test_get_job_returns_created_job():
    job = jobs.create_job()
    found = jobs.get_job(job.job_id)
    assert found is not None
    assert found.job_id == job.job_id


def test_get_job_returns_none_for_missing():
    assert jobs.get_job("nonexistent-id") is None


def test_new_job_status_is_queued():
    job = jobs.create_job()
    assert job.status == "queued"


def test_work_dir_is_created():
    job = jobs.create_job()
    assert job.work_dir is not None
    assert job.work_dir.exists()


def test_delete_job_removes_from_store():
    job = jobs.create_job()
    jobs._delete_job(job.job_id)
    assert jobs.get_job(job.job_id) is None


def test_cleanup_expired_removes_old_jobs():
    job = jobs.create_job()
    job.created_at = time.time() - 3700  # 1 hour + 100 seconds ago
    jobs.cleanup_expired()
    assert jobs.get_job(job.job_id) is None
