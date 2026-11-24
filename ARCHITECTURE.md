# Notara Architecture

How the system is meant to fit together. For module-level details see `TECHNICAL_DOCS.md`.

## 1. What exists

```
Browser (index.html + js/)  --HTTP /api-->  FastAPI (api/)  --calls-->  pipeline/  --uses-->  ML models
        PWA, playback                      routes, jobs, worker         audio → notes → tabs      Demucs, basic-pitch,
                                                                                                    BTC, SynthTab, Whisper
CLI (main.py)  --------------------------------------------------------->  pipeline/
```

- **Frontend**: static files served by the API itself (self-hosted) or by GitHub Pages (landing at `docs/index.html`).
- **API**: one process, in-memory job store, one background thread per job.
- **Pipeline**: pure Python functions, no web or job knowledge.
- **Experimental models**: `pipeline/btc/` and `pipeline/synthtab/` are nested third-party repos (gitlinks, no `.gitmodules`). A fresh clone does not contain them; the app then runs on the legacy engines.

## 2. Who owns what

| Component | Owns |
|---|---|
| `api/routes.py` | Input validation (file size, YouTube URL, allowed tracks/formats), rate limiting, HTTP contract |
| `api/jobs.py` | Job lifecycle, per-job temp directory, 1 h TTL |
| `api/worker.py` | Orchestration order of pipeline steps, progress labels, fallbacks |
| `api/main.py` | App startup, warm-loading BTC and SynthTab |
| `pipeline/separation.py` | Demucs source separation (only place that knows stem names) |
| `pipeline/transcription*.py` | Audio → notes |
| `pipeline/tuning.py` | Tuning catalog and tuning fit |
| `pipeline/key_detection.py`, `chord_detection*.py` | Key and chords |
| `pipeline/fretboard.py`, `tab_render.py` | Notes → playable positions → ASCII tab |
| `pipeline/pdf_export.py`, `midi_export.py` | File outputs |
| `pipeline/lyrics_align.py` | Lyrics ↔ audio alignment (stable-whisper) |
| `pipeline/structure_detection.py` | Song sections (intro, verse, chorus...) |
| `js/app.js` | UI state, job submission, polling, result rendering |
| `js/playback.js` | Audio playback synced with tab and chords |

## 3. What may depend on what

Allowed:

```
js/  →  HTTP /api/*  →  api/routes  →  api/worker  →  pipeline/*
main.py (CLI)  →  pipeline/*
```

Forbidden:

- `pipeline/` importing anything from `api/` (the pipeline must stay usable from the CLI and tests).
- `js/` reaching anything other than `/api/*` endpoints.
- Any module other than `api/worker.py` deciding pipeline order or fallbacks.
- Any code sending user audio, lyrics or results to a third-party service.

## 4. How data moves

Critical flow (one transcription job):

```
Upload or YouTube URL
  → POST /api/jobs            validate, rate-limit, save audio in job temp dir
  → worker.run_job (thread)
      separate (Demucs, skipped with no_separation)
      transcribe (SynthTab → fallback basic-pitch)
      key + chords (BTC → fallback legacy)
      fretboard + tab render, MIDI/PDF export
      optional: guitar 2, bass, vocals, drums, keys, lyrics, structure, rehearsal PDF
  → job.results (in memory) + files in job temp dir
  → GET /status (polling) → GET /results → GET /download/{track}/{fmt}
  → job temp dir deleted after TTL
```

## 5. What must stay true

1. **User audio never leaves the machine running Notara.** No external API call with audio, lyrics or results. YouTube download is the only outbound fetch, limited to the YouTube extractor.
2. **An experimental or optional step never fails a job.** BTC, SynthTab, lyrics, structure and rehearsal PDF are wrapped with a fallback or skipped.
3. **A model becomes the default only after it beats the current one on the benchmark** (`tests/benchmark.py`, > 5 points on the reference set). *Not met yet: BTC and SynthTab are the current defaults but the reference set does not exist.*
4. **No persistence.** Jobs live in memory and in a temp dir with a 1 h TTL. No database, no accounts.
5. **4/4 meter** is assumed everywhere (bars, chord windows, drum grid). Changing it is an architecture change, not a local fix.
6. **Validation stays server-side** in `api/routes.py`, even when the frontend also checks.
7. `pytest` passes before any commit.

## 6. When to stop

If a task would break one of the rules above (add a network call with user data, add a database or accounts, let the pipeline import the API, make a new model the default without a benchmark, drop the 4/4 assumption):

STOP → explain the conflict → show the impact → propose the smallest change, and wait for a decision.
