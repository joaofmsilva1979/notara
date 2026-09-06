import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from . import jobs
from .routes import router

_FRONTEND_DIR = Path(__file__).parent.parent
_log = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address, default_limits=["100/hour"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    jobs.cleanup_expired()

    # Warm-load ML models so first job pays no cold-start penalty.
    # Import inside lifespan — these modules are optional and must not crash startup.
    try:
        from pipeline import chord_detection_btc
        chord_detection_btc._load_model()
        _log.info("BTC model loaded")
    except Exception as exc:
        _log.warning("BTC model not available: %s — will fall back to legacy chords", exc)

    try:
        from pipeline import transcription_synthtab
        transcription_synthtab._load()
        _log.info("SynthTab model loaded")
    except Exception as exc:
        _log.warning("SynthTab model not available: %s — will fall back to basic-pitch", exc)

    yield


app = FastAPI(title="Notara API", lifespan=lifespan)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")

app.mount("/", StaticFiles(directory=str(_FRONTEND_DIR), html=True), name="frontend")
