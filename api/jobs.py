"""In-memory job store. No database — server restart clears all jobs.

Each job gets a temp directory that is deleted when the job is cleaned up.
TTL is 1 hour after job creation (enforced by cleanup_expired, called on startup).
"""
from __future__ import annotations

import shutil
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

_store: Dict[str, "Job"] = {}
_lock = threading.Lock()


@dataclass
class Job:
    job_id: str
    status: str = "queued"       # queued | running | done | error
    step: int = 0
    total_steps: int = 6
    step_label: str = ""
    error: str = ""
    work_dir: Optional[Path] = None
    results: Optional[Dict[str, Any]] = None
    created_at: float = field(default_factory=time.time)


def create_job() -> Job:
    job_id = str(uuid.uuid4())[:8]
    work_dir = Path(tempfile.mkdtemp(prefix=f"notara_{job_id}_"))
    job = Job(job_id=job_id, work_dir=work_dir)
    with _lock:
        _store[job_id] = job
    return job


def get_job(job_id: str) -> Optional[Job]:
    with _lock:
        return _store.get(job_id)


def _delete_job(job_id: str) -> None:
    with _lock:
        job = _store.pop(job_id, None)
    if job and job.work_dir and job.work_dir.exists():
        shutil.rmtree(job.work_dir, ignore_errors=True)


def cleanup_expired() -> None:
    cutoff = time.time() - 3600
    with _lock:
        expired = [jid for jid, j in _store.items() if j.created_at < cutoff]
    for jid in expired:
        _delete_job(jid)
