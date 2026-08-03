"""All API route handlers for Notara."""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from . import jobs as job_store
from . import worker as _worker

router = APIRouter()

_AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".opus"}


@router.post("/jobs")
async def create_job(
    background_tasks: BackgroundTasks,
    file: Optional[UploadFile] = File(None),
    youtube_url: Optional[str] = Form(None),
    tuning: str = Form("Standard EADGBE"),
    key: str = Form("auto"),
    multi_guitar: bool = Form(False),
    bass_tab: bool = Form(False),
    vocal_tab: bool = Form(False),
    drum_summary: bool = Form(False),
    keys_tab: bool = Form(False),
):
    if not file and not youtube_url:
        raise HTTPException(400, "Provide either a file upload or youtube_url")

    job = job_store.create_job()

    audio_path: Optional[Path] = None
    if file:
        suffix = Path(file.filename or "audio.mp3").suffix.lower()
        if suffix not in _AUDIO_EXTENSIONS:
            raise HTTPException(400, f"Unsupported file type: {suffix}")
        audio_path = job.work_dir / f"audio{suffix}"
        with open(audio_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

    params = {
        "audio_path": audio_path,
        "youtube_url": youtube_url,
        "tuning": tuning,
        "key": key,
        "multi_guitar": multi_guitar,
        "bass_tab": bass_tab,
        "vocal_tab": vocal_tab,
        "drum_summary": drum_summary,
        "keys_tab": keys_tab,
    }

    background_tasks.add_task(_worker.run_job, job.job_id, params)
    return {"job_id": job.job_id, "status": "queued"}


@router.get("/jobs/{job_id}/status")
async def get_status(job_id: str):
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return {
        "status": job.status,
        "step": job.step,
        "step_label": job.step_label,
        "total_steps": job.total_steps,
        "error": job.error,
    }


@router.get("/jobs/{job_id}/results")
async def get_results(job_id: str):
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if job.status != "done":
        raise HTTPException(409, f"Job is {job.status}")
    return job.results


@router.get("/jobs/{job_id}/audio")
async def get_audio(job_id: str):
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if job.status != "done":
        raise HTTPException(409, "Job not done yet")
    for ext in _AUDIO_EXTENSIONS:
        candidate = job.work_dir / f"audio{ext}"
        if candidate.exists():
            return FileResponse(str(candidate))
    raise HTTPException(404, "Audio file not found")


@router.get("/jobs/{job_id}/download/{track}/{fmt}")
async def download_file(job_id: str, track: str, fmt: str):
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if job.status != "done":
        raise HTTPException(409, "Job not done yet")
    allowed_tracks = {"guitar1", "guitar2", "bass", "vocals", "keys", "drums"}
    allowed_fmts = {"pdf", "txt", "midi"}
    drums_only_fmts = {"txt"}
    if track not in allowed_tracks or fmt not in allowed_fmts:
        raise HTTPException(400, "Invalid track or format")
    if track == "drums" and fmt not in drums_only_fmts:
        raise HTTPException(400, "Drums only supports txt format")
    file_path = job.work_dir / f"{track}.{fmt}"
    if not file_path.exists():
        raise HTTPException(404, f"{track}.{fmt} not available")
    return FileResponse(str(file_path), filename=f"{track}.{fmt}")
