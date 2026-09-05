# Sprint 3 — Polish + Deploy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cache Demucs models between jobs, add onboarding hints in the UI, and deploy cleanly to api.notara.app.

**Architecture:** Three isolated improvements — model caching (server startup), UX tooltip/hint (frontend only), deploy verification (ops). No new dependencies.

**Tech Stack:** Python (FastAPI lifespan), vanilla JS, Railway/Render CLI or GitHub push.

**Prerequisites:** Sprint 0 audit passed. Sprint 1+2 committed and tests green.

---

## Environment note

```bash
cd ~/Library/CloudStorage/GoogleDrive-davisthe8th@gmail.com/My\ Drive/GARAGEBAND/VALLETOFNOONE/guitar_tab_pipeline
.venv/bin/python3 -m pytest ...
```

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `api/main.py` | Modify | Warm-load BTC + SynthTab models at lifespan startup |
| `index.html` | Modify | Add onboarding hint for tuning/key options |
| `css/main.css` | Modify | Style for hint tooltip |

---

### Task 1: Warm-load BTC + SynthTab models at startup

**Files:**
- Modify: `api/main.py`

Currently Demucs is not reloaded between jobs (it's managed by the `demucs` library). But BTC and SynthTab models are lazy-loaded on the first job — adding several seconds of cold start. This task loads them at server startup so the first job doesn't pay the penalty.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_api_jobs.py` (or create `tests/test_api_startup.py`):

```python
def test_lifespan_loads_btc_and_synthtab_models(monkeypatch):
    """Lifespan calls _load_model and _load on startup."""
    from unittest.mock import MagicMock, patch, call
    import asyncio

    btc_loaded = []
    synthtab_loaded = []

    monkeypatch.setattr("pipeline.chord_detection_btc._load_model",
                        lambda: btc_loaded.append(True))
    monkeypatch.setattr("pipeline.transcription_synthtab._load",
                        lambda: synthtab_loaded.append(True))

    from api.main import lifespan
    from fastapi import FastAPI
    app = FastAPI()

    async def _run():
        async with lifespan(app):
            pass

    asyncio.run(_run())
    assert btc_loaded, "BTC model was not warm-loaded at startup"
    assert synthtab_loaded, "SynthTab model was not warm-loaded at startup"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/bin/python3 -m pytest tests/test_api_startup.py -v
```
Expected: FAIL — models not loaded at startup.

- [ ] **Step 3: Update `api/main.py` lifespan**

```python
from contextlib import asynccontextmanager
import logging
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
```

- [ ] **Step 4: Run test to verify it passes**

```bash
.venv/bin/python3 -m pytest tests/test_api_startup.py -v
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add api/main.py tests/test_api_startup.py
git commit -m "perf: warm-load BTC and SynthTab models at server startup"
```

---

### Task 2: Onboarding hints for tuning + key options

**Files:**
- Modify: `index.html`
- Modify: `css/main.css`

When a user doesn't change tuning/key, the defaults (Standard EADGBE, auto) are used silently. This adds a small hint line under each select, visible only when the default is selected, nudging users to verify.

- [ ] **Step 1: Add hint markup to `index.html`**

In the tuning `<select>` block, add after the `<select>`:

```html
<p class="option-hint" id="tuning-hint">
  Tip: if the tab looks off, try a different tuning — Drop D and Eb Standard are common.
</p>
```

In the key `<select>` block, add after the `<select>`:

```html
<p class="option-hint" id="key-hint">
  "Auto" works for most songs. Override if you know the key.
</p>
```

- [ ] **Step 2: Add hint styles to `css/main.css`**

```css
.option-hint {
  font-size: 0.72rem;
  color: var(--muted);
  margin: 2px 0 0 0;
  line-height: 1.4;
}
```

- [ ] **Step 3: Hide hint when non-default is selected**

Add to `js/app.js` (inside the DOMContentLoaded setup or near the tuning select wiring):

```js
// Hide tuning hint when user picks a non-default tuning
document.getElementById('tuning-select')?.addEventListener('change', e => {
  const hint = document.getElementById('tuning-hint');
  if (hint) hint.style.display = e.target.value === 'Standard EADGBE' ? '' : 'none';
});

// Hide key hint when user picks a specific key
document.getElementById('key-select')?.addEventListener('change', e => {
  const hint = document.getElementById('key-hint');
  if (hint) hint.style.display = e.target.value === 'auto' ? '' : 'none';
});
```

- [ ] **Step 4: Commit**

```bash
git add index.html css/main.css js/app.js
git commit -m "ux: onboarding hints for tuning and key selects"
```

---

### Task 3: Deploy to api.notara.app

**Files:** None — ops only.

- [ ] **Step 1: Push main to GitHub**

```bash
git push origin main
```

- [ ] **Step 2: Verify GitHub Pages frontend**

Open `https://joaofmsilva1979.github.io/notara/` (or the configured Pages URL). Confirm:
- Page loads without console errors
- Lyrics section visible in the upload panel
- Tab switcher shows "Lyrics" option after a test transcription

- [ ] **Step 3: Verify backend on Railway/Render**

```bash
curl https://api.notara.app/api/health
```
Expected response:
```json
{"status": "ok", "python": "...", "packages": {...}}
```

Check that the deploy logs show:
```
INFO:api.main:BTC model loaded
INFO:api.main:SynthTab model loaded
```

If either model fails to load on the hosted instance (VRAM, disk space), the fallback logging confirms it degraded gracefully.

- [ ] **Step 4: Smoke test end-to-end**

Upload a short WAV (< 30 s) via the web UI. Verify:
1. Progress steps display correctly (including the new lyrics step if lyrics were provided)
2. Guitar tab renders with BTC chord labels (richer vocab: maj7, m7, sus4, etc.)
3. Download buttons work for TXT and PDF
4. Audio playback + bar highlight sync works

- [ ] **Step 5: Tag the release**

```bash
git tag v1.0.0 -m "Notara v1.0.0 — lyrics, BTC chords, SynthTab transcription"
git push origin v1.0.0
```
