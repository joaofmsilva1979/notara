"""All API route handlers for Notara."""
from __future__ import annotations

import importlib.metadata
import io
import shutil
import sys
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from slowapi import Limiter
from slowapi.util import get_remote_address

from . import jobs as job_store
from . import worker as _worker

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)

_AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".opus"}

MAX_UPLOAD_BYTES = 150 * 1024 * 1024  # 150 MB

_ALLOWED_YT_HOSTS = {"youtube.com", "www.youtube.com", "youtu.be", "www.youtu.be"}


def _is_valid_youtube_url(url: str) -> bool:
    """Strict domain check via urlparse — rejects regex-bypassable variants."""
    try:
        p = urlparse(url)
    except Exception:
        return False
    return (
        p.scheme in ("https", "http")
        and p.netloc in _ALLOWED_YT_HOSTS
        and bool(p.path or p.query)
    )


@router.get("/health")
async def health():
    _PACKAGES = ["demucs", "basic-pitch", "librosa", "yt-dlp", "fastapi", "torch"]
    versions = {}
    for pkg in _PACKAGES:
        try:
            versions[pkg] = importlib.metadata.version(pkg)
        except importlib.metadata.PackageNotFoundError:
            versions[pkg] = "NOT INSTALLED"
    yt_dlp_path = shutil.which("yt-dlp")
    return {
        "status": "ok",
        "python": sys.version,
        "packages": versions,
        "yt_dlp_in_path": yt_dlp_path or "NOT FOUND",
    }


@router.post("/jobs")
@limiter.limit("10/hour")
async def create_job(
    request: Request,
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
    lyrics_file: Optional[UploadFile] = File(None),
    lyrics_text: Optional[str] = Form(""),
):
    if not file and not youtube_url:
        raise HTTPException(400, "Provide either a file upload or youtube_url")

    if youtube_url and not _is_valid_youtube_url(youtube_url):
        raise HTTPException(status_code=400, detail="Invalid YouTube URL.")

    job = job_store.create_job()

    audio_path: Optional[Path] = None
    if file:
        suffix = Path(file.filename or "audio.mp3").suffix.lower()
        if suffix not in _AUDIO_EXTENSIONS:
            raise HTTPException(400, f"Unsupported file type: {suffix}")
        content = await file.read()
        if len(content) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="File too large. Maximum size is 150 MB.")
        file.file = io.BytesIO(content)
        file.size = len(content)
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

    # Resolve lyrics: file takes priority over pasted text
    lyrics_raw: Optional[str] = None
    if lyrics_file and lyrics_file.filename:
        suffix = Path(lyrics_file.filename).suffix.lower()
        raw_bytes = await lyrics_file.read()
        if suffix == ".docx":
            try:
                from docx import Document
                import io as _io
                doc = Document(_io.BytesIO(raw_bytes))
                lyrics_raw = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
            except Exception:
                lyrics_raw = None
        else:
            try:
                lyrics_raw = raw_bytes.decode("utf-8", errors="replace")
            except Exception:
                lyrics_raw = None
    elif lyrics_text and lyrics_text.strip():
        lyrics_raw = lyrics_text.strip()

    params["lyrics_raw"] = lyrics_raw

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
    allowed_tracks = {"guitar1", "guitar2", "bass", "vocals", "keys", "drums", "lyrics"}
    allowed_fmts = {"pdf", "txt", "midi"}
    if track not in allowed_tracks or fmt not in allowed_fmts:
        raise HTTPException(400, "Invalid track or format")
    if track == "drums" and fmt not in {"txt"}:
        raise HTTPException(400, "Drums only supports txt format")
    if track == "lyrics" and fmt not in {"txt", "pdf"}:
        raise HTTPException(400, "Lyrics supports txt and pdf formats only")
    file_path = job.work_dir / f"{track}.{fmt}"
    if not file_path.exists():
        raise HTTPException(404, f"{track}.{fmt} not available")
    return FileResponse(str(file_path), filename=f"{track}.{fmt}")
