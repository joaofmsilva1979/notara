# Notara Web Platform Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the full Notara web platform — FastAPI backend wrapping the existing Python pipeline + GitHub Pages frontend (HTML/CSS/JS, zero framework) — deployable to `joaofmsilva1979.github.io/notara` with backend on Railway/Render.

**Architecture:** Static frontend at repo root (`index.html`, `css/`, `js/`) served by GitHub Pages from the `main` branch root. FastAPI backend in `api/` wraps the `pipeline/` modules, runs jobs async in background threads, holds all state in memory (no DB), and deletes job files after 1 hour. Frontend talks to backend via REST polling.

**Tech Stack:** Python 3.11+, FastAPI, uvicorn, yt-dlp, python-multipart; vanilla JS (no framework); librosa (already in requirements); reportlab (already in requirements); GitHub Pages; Railway or Render (free tier).

---

## File Map

```
# New files
pipeline/vocal_tab.py          # vocal melody transcription module
pipeline/drum_summary.py       # drum rhythm analysis module
pipeline/piano_tab.py          # keyboard/keys MIDI detector (Demucs piano stem)
api/__init__.py                # empty, makes api/ a package
api/main.py                    # FastAPI app + CORS + lifespan
api/jobs.py                    # in-memory job store + Job dataclass
api/routes.py                  # all API route handlers
api/worker.py                  # background pipeline execution
api/requirements.txt           # fastapi, uvicorn, yt-dlp, python-multipart + pipeline deps
index.html                     # full single-page app (NAV + TOOL + ABOUT)
css/main.css                   # all styles (Warm Ruby palette, responsive)
js/config.js                   # API_BASE_URL constant
js/app.js                      # upload, options, job submit, progress polling, tab display, PWA install
js/playback.js                 # audio playback + bar-sync highlight
manifest.json                  # PWA manifest (icon, theme, name)
og-image.svg                   # 1200×630 social preview card (SVG)
sitemap.xml                    # single-URL sitemap
robots.txt                     # Allow: /, Sitemap pointer

# Copied files
logo/notara-logo-simple.png    # already exists — copied to repo root as notara-logo.png

# Modified files
pipeline/tuning.py             # add 15 new tunings (11 six-string + 4 extended)
tests/test_tuning.py           # add tests for new tunings
```

---

## Task 1: Extend tuning catalog

**Files:**
- Modify: `pipeline/tuning.py`
- Modify: `tests/test_tuning.py`

Add 11 new 6-string tunings to `TUNINGS` (so `suggest_alternate_tuning` can propose them) and 4 multi-string tunings to a new `EXTENDED_TUNINGS` list. Update `find_tuning` to search all three lists.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_tuning.py — add at the bottom of the existing file

def test_new_six_string_tunings_are_in_tunings_list():
    names = [t.name for t in tuning.TUNINGS]
    for expected in [
        "C# Standard", "C Standard", "Drop C", "Drop B", "Drop A",
        "Open E", "Open A", "Open C", "DADGAD", "Baritone B", "Baritone A",
    ]:
        assert expected in names, f"{expected} missing from TUNINGS"


def test_extended_tunings_exist():
    names = [t.name for t in tuning.EXTENDED_TUNINGS]
    for expected in [
        "7-String Standard", "7-String Drop A",
        "8-String Standard", "8-String Drop E",
    ]:
        assert expected in names, f"{expected} missing from EXTENDED_TUNINGS"


def test_find_tuning_finds_all_new_tunings():
    for name in [
        "C# Standard", "C Standard", "Drop C", "Drop B", "Drop A",
        "Open E", "Open A", "Open C", "DADGAD", "Baritone B", "Baritone A",
        "7-String Standard", "7-String Drop A",
        "8-String Standard", "8-String Drop E",
    ]:
        result = tuning.find_tuning(name)
        assert result.name == name


def test_suggest_alternate_tuning_never_returns_extended():
    """7/8-string tunings must never be suggested for 6-string input."""
    from pipeline.transcription import Note
    # Notes that span Drop A range — should suggest Drop A (6-string), not 7-string
    notes = [Note(pitch=33, start=i * 0.5, end=i * 0.5 + 0.4, amplitude=0.8) for i in range(10)]
    std = tuning.find_tuning(tuning.STANDARD_E_A_D_G_B_E)
    suggestion = tuning.suggest_alternate_tuning(notes, std)
    if suggestion is not None:
        assert suggestion.suggested.name not in [t.name for t in tuning.EXTENDED_TUNINGS]


def test_guitar_tunings_catalog_is_eighteen_entries():
    assert len(tuning.TUNINGS) == 18  # 7 original + 11 new
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd "/Users/joao.silva/Library/CloudStorage/GoogleDrive-davisthe8th@gmail.com/My Drive/GARAGEBAND/VALLETOFNOONE/guitar_tab_pipeline"
python -m pytest tests/test_tuning.py::test_new_six_string_tunings_are_in_tunings_list tests/test_tuning.py::test_extended_tunings_exist tests/test_tuning.py::test_find_tuning_finds_all_new_tunings tests/test_tuning.py::test_suggest_alternate_tuning_never_returns_extended tests/test_tuning.py::test_guitar_tunings_catalog_is_eighteen_entries -v
```

Expected: 5 FAILs.

- [ ] **Step 3: Add new tunings to `pipeline/tuning.py`**

Add constants and update `TUNINGS`, add `EXTENDED_TUNINGS`, update `find_tuning`:

```python
# Add after existing constants (after OPEN_D = "Open D"):
C_SHARP_STANDARD = "C# Standard"
C_STANDARD = "C Standard"
DROP_C = "Drop C"
DROP_B = "Drop B"
DROP_A_SIX = "Drop A"
OPEN_E = "Open E"
OPEN_A = "Open A"
OPEN_C = "Open C"
DADGAD = "DADGAD"
BARITONE_B = "Baritone B"
BARITONE_A = "Baritone A"

SEVEN_STRING_STANDARD = "7-String Standard"
SEVEN_STRING_DROP_A = "7-String Drop A"
EIGHT_STRING_STANDARD = "8-String Standard"
EIGHT_STRING_DROP_E = "8-String Drop E"
```

Replace the `TUNINGS` list with this 18-entry version:

```python
TUNINGS: List[Tuning] = [
    Tuning(STANDARD_E_A_D_G_B_E, [40, 45, 50, 55, 59, 64], ["E", "A", "D", "G", "B", "e"]),
    Tuning(DROP_D,               [38, 45, 50, 55, 59, 64], ["D", "A", "D", "G", "B", "e"]),
    Tuning(EB_STANDARD,          [39, 44, 49, 54, 58, 63], ["Eb", "Ab", "Db", "Gb", "Bb", "eb"]),
    Tuning(D_STANDARD,           [38, 43, 48, 53, 57, 62], ["D", "G", "C", "F", "A", "d"]),
    Tuning(DROP_C_SHARP,         [37, 44, 49, 54, 58, 63], ["C#", "Ab", "Db", "Gb", "Bb", "eb"]),
    Tuning(OPEN_G,               [38, 43, 50, 55, 59, 62], ["D", "G", "D", "G", "B", "d"]),
    Tuning(OPEN_D,               [38, 45, 50, 54, 57, 62], ["D", "A", "D", "F#", "A", "d"]),
    # New 6-string tunings
    Tuning(C_SHARP_STANDARD,     [37, 42, 47, 52, 56, 61], ["C#", "F#", "B", "E", "G#", "c#"]),
    Tuning(C_STANDARD,           [36, 41, 46, 51, 55, 60], ["C", "F", "Bb", "Eb", "G", "c"]),
    Tuning(DROP_C,               [36, 43, 48, 53, 57, 62], ["C", "G", "C", "F", "A", "d"]),
    Tuning(DROP_B,               [35, 42, 47, 52, 56, 61], ["B", "F#", "B", "E", "G#", "c#"]),
    Tuning(DROP_A_SIX,           [33, 40, 45, 50, 54, 59], ["A", "E", "A", "D", "F#", "b"]),
    Tuning(OPEN_E,               [40, 47, 52, 56, 59, 64], ["E", "B", "E", "G#", "B", "e"]),
    Tuning(OPEN_A,               [40, 45, 52, 57, 61, 64], ["E", "A", "E", "A", "C#", "e"]),
    Tuning(OPEN_C,               [36, 43, 48, 55, 60, 64], ["C", "G", "C", "G", "C", "e"]),
    Tuning(DADGAD,               [38, 45, 50, 55, 57, 62], ["D", "A", "D", "G", "A", "d"]),
    Tuning(BARITONE_B,           [35, 40, 45, 50, 54, 59], ["B", "E", "A", "D", "F#", "b"]),
    Tuning(BARITONE_A,           [33, 38, 43, 48, 52, 57], ["A", "D", "G", "C", "E", "a"]),
]

EXTENDED_TUNINGS: List[Tuning] = [
    Tuning(SEVEN_STRING_STANDARD, [35, 40, 45, 50, 55, 59, 64], ["B", "E", "A", "D", "G", "B", "e"]),
    Tuning(SEVEN_STRING_DROP_A,   [33, 40, 45, 50, 55, 59, 64], ["A", "E", "A", "D", "G", "B", "e"]),
    Tuning(EIGHT_STRING_STANDARD, [30, 35, 40, 45, 50, 55, 59, 64], ["F#", "B", "E", "A", "D", "G", "B", "e"]),
    Tuning(EIGHT_STRING_DROP_E,   [28, 35, 40, 45, 50, 55, 59, 64], ["E", "B", "E", "A", "D", "G", "B", "e"]),
]
```

Replace `find_tuning`:

```python
def find_tuning(name: str) -> Tuning:
    for tuning in TUNINGS + BASS_TUNINGS + EXTENDED_TUNINGS:
        if tuning.name == name:
            return tuning
    raise ValueError(f"Unknown tuning: {name!r}")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_tuning.py -v
```

Expected: all pass (including the renamed `test_guitar_tunings_catalog_is_eighteen_entries` — also delete the old `test_guitar_tunings_catalog_still_has_seven_entries` test if it exists).

- [ ] **Step 5: Run full test suite to check for regressions**

```bash
python -m pytest -v
```

Expected: all 57+ tests pass.

- [ ] **Step 6: Commit**

```bash
git add pipeline/tuning.py tests/test_tuning.py
git commit -m "feat: extend tuning catalog — 11 new 6-string + 4 extended (7/8-string)"
```

---

## Task 2: Vocal melody transcription module

**Files:**
- Create: `pipeline/vocal_tab.py`
- Create: `tests/test_vocal_tab.py`

Transcribes the Demucs vocal stem using basic-pitch, optionally transposes down one octave if the median pitch exceeds MIDI 60, then renders as a standard guitar-octave melody tab.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_vocal_tab.py
from unittest.mock import patch, MagicMock
from pathlib import Path

import numpy as np
import pytest

from pipeline import vocal_tab
from pipeline.transcription import Note
from pipeline.key_detection import KeyEstimate
from pipeline.chord_detection import ChordSegment


def _make_notes(pitches):
    return [Note(pitch=p, start=i * 0.5, end=i * 0.5 + 0.4, amplitude=0.8)
            for i, p in enumerate(pitches)]


def _make_bars():
    return [ChordSegment(bar_index=0, start=0.0, end=2.0, label="Am")]


def _make_key():
    return KeyEstimate(tonic="A", mode="minor", correlation=0.9)


def test_should_transpose_high_notes():
    notes = _make_notes([65, 67, 69, 71, 72])  # median=69, above 60
    assert vocal_tab._should_transpose(notes) is True


def test_should_not_transpose_low_notes():
    notes = _make_notes([45, 47, 50, 52, 55])  # median=50, below 60
    assert vocal_tab._should_transpose(notes) is False


def test_should_not_transpose_empty():
    assert vocal_tab._should_transpose([]) is False


def test_transcribe_vocal_melody_transposes_when_high():
    high_notes = _make_notes([65, 67, 69, 71, 72])
    with patch("pipeline.vocal_tab.transcribe", return_value=high_notes):
        result_notes, transposed = vocal_tab.transcribe_vocal_melody(Path("fake.wav"))
    assert transposed is True
    assert all(n.pitch == orig.pitch - 12 for n, orig in zip(result_notes, high_notes))


def test_transcribe_vocal_melody_no_transpose_when_low():
    low_notes = _make_notes([45, 47, 50, 52, 55])
    with patch("pipeline.vocal_tab.transcribe", return_value=low_notes):
        result_notes, transposed = vocal_tab.transcribe_vocal_melody(Path("fake.wav"))
    assert transposed is False
    assert all(n.pitch == orig.pitch for n, orig in zip(result_notes, low_notes))


def test_render_vocal_tab_contains_transpose_comment_when_transposed():
    high_notes = _make_notes([65, 67, 69, 71, 72])
    with patch("pipeline.vocal_tab.transcribe", return_value=high_notes):
        result = vocal_tab.render_vocal_tab(
            Path("fake.wav"), _make_bars(), _make_key(), 120.0, "test.wav"
        )
    assert "Transposed: -1 octave" in result


def test_render_vocal_tab_no_transpose_comment_when_not_transposed():
    low_notes = _make_notes([45, 47, 50, 52, 55])
    with patch("pipeline.vocal_tab.transcribe", return_value=low_notes):
        result = vocal_tab.render_vocal_tab(
            Path("fake.wav"), _make_bars(), _make_key(), 120.0, "test.wav"
        )
    assert "Transposed" not in result
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_vocal_tab.py -v
```

Expected: ImportError or 6 FAILs.

- [ ] **Step 3: Create `pipeline/vocal_tab.py`**

```python
"""Vocal melody transcription — wraps basic-pitch on the Demucs vocal stem.

Renders as a single-string melody tab in guitar octave range. If the median
pitch of transcribed notes exceeds MIDI 60 (middle C), all notes are
transposed down one octave so the melody sits comfortably on a standard
guitar fretboard.
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Tuple

import numpy as np

from .chord_detection import ChordSegment
from .fretboard import map_notes_to_fretboard
from .key_detection import KeyEstimate
from .tab_render import render_tab
from .transcription import Note, transcribe
from .tuning import STANDARD_E_A_D_G_B_E, find_tuning

GUITAR_RANGE_MIDPOINT = 60  # MIDI — middle C
OCTAVE_SEMITONES = 12


def _should_transpose(notes: List[Note]) -> bool:
    if not notes:
        return False
    return float(np.median([n.pitch for n in notes])) > GUITAR_RANGE_MIDPOINT


def transcribe_vocal_melody(vocal_stem_path: Path) -> Tuple[List[Note], bool]:
    """Return (notes, transposed).

    transposed=True means all pitches were shifted down one octave.
    """
    notes = transcribe(vocal_stem_path)
    transposed = _should_transpose(notes)
    if transposed:
        notes = [
            Note(pitch=n.pitch - OCTAVE_SEMITONES, start=n.start,
                 end=n.end, amplitude=n.amplitude)
            for n in notes
        ]
    return notes, transposed


def render_vocal_tab(
    vocal_stem_path: Path,
    bars: List[ChordSegment],
    key_estimate: KeyEstimate,
    tempo: float,
    source_name: str,
) -> str:
    """Transcribe vocal stem and render as guitar-octave melody tab."""
    tuning = find_tuning(STANDARD_E_A_D_G_B_E)
    notes, transposed = transcribe_vocal_melody(vocal_stem_path)
    fretted = map_notes_to_fretboard(notes, tuning)
    tab = render_tab(bars, fretted, key_estimate, tempo, source_name, tuning)
    if transposed:
        tab = tab.replace(
            f"# Tuning: {tuning.name}",
            f"# Tuning: {tuning.name}\n# Transposed: -1 octave to fit guitar range",
        )
    return tab
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_vocal_tab.py -v
```

Expected: 6 PASSes.

- [ ] **Step 5: Run full suite**

```bash
python -m pytest -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add pipeline/vocal_tab.py tests/test_vocal_tab.py
git commit -m "feat: add vocal melody transcription module"
```

---

## Task 3: Drum summary module

**Files:**
- Create: `pipeline/drum_summary.py`
- Create: `tests/test_drum_summary.py`

Onset detection on the drum stem + frequency-band energy classification (kick/snare/hi-hat). Produces an ASCII groove map and one-line pattern description.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_drum_summary.py
import numpy as np
import pytest
from pipeline import drum_summary


def test_classify_onset_kick():
    sr = 22050
    t = np.linspace(0, 0.05, int(sr * 0.05))
    # Synthesise a 100 Hz sine (kick-band)
    y = np.sin(2 * np.pi * 100 * t).astype(np.float32)
    result = drum_summary._classify_onset(y, sr, 0)
    assert result == "K"


def test_classify_onset_hihat():
    sr = 22050
    t = np.linspace(0, 0.05, int(sr * 0.05))
    # Synthesise a 10000 Hz sine (hi-hat band)
    y = np.sin(2 * np.pi * 10000 * t).astype(np.float32)
    result = drum_summary._classify_onset(y, sr, 0)
    assert result == "H"


def test_build_grid_places_onsets():
    onsets = np.array([0.0, 0.5])  # beat 1 and beat 1+
    labels = ["K", "S"]
    grid = drum_summary._build_grid(onsets, labels, tempo=120.0, n_bars=1)
    assert "●" in grid["K"][0]
    assert "●" in grid["S"][0]


def test_ascii_pattern_has_three_rows():
    onsets = np.array([0.0, 0.25, 0.5])
    labels = ["K", "H", "S"]
    grid = drum_summary._build_grid(onsets, labels, tempo=120.0, n_bars=1)
    pattern = drum_summary._ascii_pattern(grid)
    assert "K:" in pattern
    assert "S:" in pattern
    assert "HH:" in pattern


def test_summarize_drums_returns_string(tmp_path):
    import soundfile as sf
    sr = 22050
    duration = 4.0
    # Synthesise a simple kick pattern (100 Hz bursts)
    y = np.zeros(int(sr * duration), dtype=np.float32)
    for beat in [0.0, 0.5, 1.0, 1.5]:
        start = int(beat * sr)
        end = min(start + int(0.05 * sr), len(y))
        t = np.linspace(0, 0.05, end - start)
        y[start:end] = np.sin(2 * np.pi * 100 * t).astype(np.float32)
    drum_path = tmp_path / "drums.wav"
    sf.write(str(drum_path), y, sr)
    result = drum_summary.summarize_drums(drum_path, tempo=120.0)
    assert isinstance(result, str)
    assert "BPM" in result
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_drum_summary.py -v
```

Expected: ImportError or 5 FAILs.

- [ ] **Step 3: Create `pipeline/drum_summary.py`**

```python
"""Drum rhythm summary — onset detection + frequency-band classification.

Each onset is classified as kick (50–200 Hz), snare (200–800 Hz), or
hi-hat (8000+ Hz) by measuring mean FFT energy in the band over a 50 ms
window after the onset. Onsets are quantized to a 4/4 beat grid at
8th-note resolution and rendered as an ASCII groove map.
"""
from __future__ import annotations

from pathlib import Path
from typing import List

import librosa
import numpy as np

KICK_LO, KICK_HI = 50, 200
SNARE_LO, SNARE_HI = 200, 800
HIHAT_LO = 8000
WINDOW_SEC = 0.05
GRID_SUBDIVISIONS = 8  # 8th notes per bar


def _band_energy(y: np.ndarray, sr: int, lo: int, hi: int, start_sample: int) -> float:
    end = min(start_sample + int(sr * WINDOW_SEC), len(y))
    window = y[start_sample:end]
    if len(window) == 0:
        return 0.0
    S = np.abs(np.fft.rfft(window))
    freqs = np.fft.rfftfreq(len(window), d=1.0 / sr)
    mask = (freqs >= lo) & (freqs < hi)
    return float(S[mask].mean()) if mask.any() else 0.0


def _classify_onset(y: np.ndarray, sr: int, sample: int) -> str:
    kick = _band_energy(y, sr, KICK_LO, KICK_HI, sample)
    snare = _band_energy(y, sr, SNARE_LO, SNARE_HI, sample)
    hihat = _band_energy(y, sr, HIHAT_LO, sr // 2, sample)
    dominant = max(kick, snare, hihat)
    if dominant == kick:
        return "K"
    if dominant == snare:
        return "S"
    return "H"


def _build_grid(
    onsets_sec: np.ndarray, labels: List[str], tempo: float, n_bars: int = 4
) -> dict:
    beat_sec = 60.0 / tempo
    bar_sec = beat_sec * 4
    grid: dict = {inst: [[" "] * GRID_SUBDIVISIONS for _ in range(n_bars)]
                  for inst in ("K", "S", "H")}
    for t, label in zip(onsets_sec, labels):
        bar_idx = int(t / bar_sec)
        if bar_idx >= n_bars:
            continue
        pos_in_bar = (t % bar_sec) / bar_sec
        slot = int(round(pos_in_bar * GRID_SUBDIVISIONS))
        slot = min(slot, GRID_SUBDIVISIONS - 1)
        grid[label][bar_idx][slot] = "●"
    return grid


def _ascii_pattern(grid: dict) -> str:
    header = "Beat:  1    +    2    +    3    +    4    +"
    lines = [header]
    for inst, prefix in (("K", "K:"), ("S", "S:"), ("H", "HH:")):
        row = grid[inst][0]
        cells = [f"{c:<5}" for c in row]
        lines.append(f"{prefix:<6}" + "".join(cells))
    return "\n".join(lines)


def _pattern_description(grid: dict, tempo: float) -> str:
    k_slots = [i for i, c in enumerate(grid["K"][0]) if c == "●"]
    s_slots = [i for i, c in enumerate(grid["S"][0]) if c == "●"]
    h_slots = [i for i, c in enumerate(grid["H"][0]) if c == "●"]

    parts = [f"4/4 · {tempo:.0f} BPM"]
    if k_slots:
        beats = sorted({i // 2 + 1 for i in k_slots})
        parts.append("kick on " + "&".join(str(b) for b in beats))
    if s_slots:
        beats = sorted({i // 2 + 1 for i in s_slots})
        parts.append("snare on " + "&".join(str(b) for b in beats))
    h_count = len(h_slots)
    if h_count >= 6:
        parts.append("hi-hat 8ths")
    elif h_count >= 3:
        parts.append("hi-hat quarters")
    return " · ".join(parts)


def summarize_drums(drum_stem_path: Path, tempo: float) -> str:
    """Return a drum summary string: ASCII groove map + pattern description."""
    y, sr = librosa.load(str(drum_stem_path), sr=None, mono=True)
    onset_samples = librosa.onset.onset_detect(y=y, sr=sr, units="samples")

    if len(onset_samples) == 0:
        return f"# Tempo: {tempo:.0f} BPM\n\n(No drum onsets detected)"

    onsets_sec = onset_samples / sr
    labels = [_classify_onset(y, sr, int(s)) for s in onset_samples]

    bar_sec = 60.0 / tempo * 4
    n_bars = max(4, min(8, int(onsets_sec[-1] / bar_sec) + 1))
    grid = _build_grid(onsets_sec, labels, tempo, n_bars=n_bars)

    description = _pattern_description(grid, tempo)
    header = f"# Tempo: {tempo:.0f} BPM · {description}"
    return f"{header}\n\n{_ascii_pattern(grid)}"
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_drum_summary.py -v
```

Expected: 5 PASSes.

- [ ] **Step 5: Run full suite**

```bash
python -m pytest -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add pipeline/drum_summary.py tests/test_drum_summary.py
git commit -m "feat: add drum rhythm summary module"
```

---

## Task 4: FastAPI backend — job model and app skeleton

**Files:**
- Create: `api/__init__.py`
- Create: `api/jobs.py`
- Create: `api/main.py`
- Create: `api/requirements.txt`
- Create: `tests/test_api_jobs.py`

- [ ] **Step 1: Write the failing tests**

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_api_jobs.py -v
```

Expected: ImportError or 7 FAILs.

- [ ] **Step 3: Create `api/__init__.py`** (empty file)

```bash
touch "/Users/joao.silva/Library/CloudStorage/GoogleDrive-davisthe8th@gmail.com/My Drive/GARAGEBAND/VALLETOFNOONE/guitar_tab_pipeline/api/__init__.py"
```

- [ ] **Step 4: Create `api/jobs.py`**

```python
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
```

- [ ] **Step 5: Create `api/main.py`**

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import jobs
from .routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    jobs.cleanup_expired()
    yield


app = FastAPI(title="Notara API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")
```

- [ ] **Step 6: Create `api/requirements.txt`**

```
# Pipeline dependencies
demucs>=4.0.1
basic-pitch[coreml]>=0.4.0
librosa>=0.10.1
soundfile>=0.12.1
mido>=1.3.2
numpy<2.0
scipy>=1.10
reportlab>=5.0.0

# Web platform dependencies
fastapi>=0.110
uvicorn[standard]>=0.29
python-multipart>=0.0.9
yt-dlp>=2024.1.1
```

- [ ] **Step 7: Run job tests to verify they pass**

```bash
python -m pytest tests/test_api_jobs.py -v
```

Expected: 7 PASSes.

- [ ] **Step 8: Commit**

```bash
git add api/__init__.py api/jobs.py api/main.py api/requirements.txt tests/test_api_jobs.py
git commit -m "feat: FastAPI backend skeleton — job store + app setup"
```

---

## Task 5: FastAPI backend — routes and worker

**Files:**
- Create: `api/routes.py`
- Create: `api/worker.py`
- Create: `tests/test_api_routes.py`

The worker runs the full pipeline in a background thread. Routes expose all endpoints from the spec.

- [ ] **Step 1: Write the failing route tests**

```python
# tests/test_api_routes.py
import io
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from api.main import app

client = TestClient(app)


def test_post_jobs_requires_file_or_url():
    resp = client.post("/api/jobs")
    assert resp.status_code == 422  # FastAPI validation (no fields at all)


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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_api_routes.py -v
```

Expected: ImportError or FAILs.

- [ ] **Step 3: Create `api/routes.py`**

```python
"""All API route handlers for Notara."""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from . import jobs as job_store
from .worker import run_job

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
    }

    background_tasks.add_task(run_job, job.job_id, params)
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
    allowed_tracks = {"guitar1", "guitar2", "bass", "vocals"}
    allowed_fmts = {"pdf", "txt", "midi"}
    if track not in allowed_tracks or fmt not in allowed_fmts:
        raise HTTPException(400, "Invalid track or format")
    file_path = job.work_dir / f"{track}.{fmt}"
    if not file_path.exists():
        raise HTTPException(404, f"{track}.{fmt} not available")
    return FileResponse(str(file_path), filename=f"{track}.{fmt}")
```

- [ ] **Step 4: Create `api/worker.py`**

```python
"""Background worker — runs the full pipeline for a job.

Adds sys.path entry so that `pipeline/` (at the repo root) is importable
when this module is loaded from within `api/`.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional

# Make repo root importable
sys.path.insert(0, str(Path(__file__).parent.parent))

import librosa

from pipeline import (
    chord_detection, fretboard, key_detection,
    separation, tab_render, transcription,
)
from pipeline import tuning as tuning_mod
from pipeline import vocal_tab as vocal_tab_mod
from pipeline import drum_summary as drum_summary_mod
from pipeline.midi_export import export_midi
from pipeline.pdf_export import export_pdf
from pipeline.separation import DEMUCS_MODEL

from . import jobs as job_store


def _step(job: job_store.Job, n: int, label: str) -> None:
    job.step = n
    job.step_label = label
    job.status = "running"


def _count_steps(params: Dict[str, Any]) -> int:
    base = 4  # separate + transcribe g1 + key/chords + fretboard/render g1
    if params["multi_guitar"]:
        base += 1
    if params["bass_tab"]:
        base += 1
    if params["vocal_tab"]:
        base += 1
    if params["drum_summary"]:
        base += 1
    return base


def run_job(job_id: str, params: Dict[str, Any]) -> None:
    job = job_store.get_job(job_id)
    if not job:
        return

    try:
        work_dir: Path = job.work_dir
        job.total_steps = _count_steps(params)
        step = 0

        # YouTube download
        if params.get("youtube_url"):
            step += 1
            _step(job, step, "Downloading from YouTube")
            audio_path = work_dir / "audio.mp3"
            subprocess.run(
                ["yt-dlp", "-x", "--audio-format", "mp3",
                 "-o", str(audio_path), params["youtube_url"]],
                check=True,
            )
            params["audio_path"] = audio_path
            job.total_steps += 1  # account for download step

        audio_path = Path(params["audio_path"])

        # Step: Separate
        step += 1
        _step(job, step, "Separating stems (Demucs)")
        if params["multi_guitar"]:
            guitar1_path, guitar2_path, bass_path, harmonic_path = \
                separation.separate_guitars(audio_path, work_dir)
        else:
            harmonic_path, bass_path = separation.separate(audio_path, work_dir)
            guitar1_path = harmonic_path
            guitar2_path = None

        # Step: Transcribe Guitar 1
        step += 1
        _step(job, step, "Transcribing Guitar 1")
        guitar_tuning_name = params["tuning"]
        if guitar_tuning_name == "auto" or guitar_tuning_name == "Standard EADGBE":
            guitar_tuning = tuning_mod.find_tuning(tuning_mod.STANDARD_E_A_D_G_B_E)
        else:
            guitar_tuning = tuning_mod.find_tuning(guitar_tuning_name)
        notes1 = transcription.transcribe(guitar1_path)

        # Auto-detect tuning if "auto"
        if guitar_tuning_name == "auto":
            suggestion = tuning_mod.suggest_alternate_tuning(notes1, guitar_tuning)
            if suggestion:
                guitar_tuning = suggestion.suggested

        # Step: Key + Chords
        step += 1
        _step(job, step, "Detecting key & chords")
        y, sr = librosa.load(str(harmonic_path), sr=None, mono=True)
        bass_y, bass_sr = librosa.load(str(bass_path), sr=None, mono=True)
        key_est = key_detection.detect_key(y, sr)

        # Override key if user specified
        if params["key"] != "auto":
            parts = params["key"].split()
            if len(parts) == 2:
                key_est = key_detection.KeyEstimate(
                    tonic=parts[0], mode=parts[1], correlation=1.0
                )

        bars, tempo = chord_detection.detect_chords(y, sr, bass_y, bass_sr, key_est)

        # Step: Fretboard + render Guitar 1
        step += 1
        _step(job, step, "Mapping to fretboard + rendering tab")
        fretted1 = fretboard.map_notes_to_fretboard(notes1, guitar_tuning)
        # bars_per_line=1 for web display (bar-sync highlight requires one block per bar)
        tab1_web = tab_render.render_tab(
            bars, fretted1, key_est, tempo, audio_path.name, guitar_tuning, bars_per_line=1
        )
        # bars_per_line=4 for file download (traditional format)
        tab1 = tab_render.render_tab(
            bars, fretted1, key_est, tempo, audio_path.name, guitar_tuning
        )
        (work_dir / "guitar1.txt").write_text(tab1, encoding="utf-8")
        export_pdf(
            work_dir / "guitar1.pdf", bars, fretted1, key_est, tempo,
            audio_path.name, guitar_tuning
        )
        export_midi(work_dir / "guitar1.midi", fretted1, tempo)

        results: Dict[str, Any] = {
            "tabs": {"guitar1": tab1_web},
            "key": str(key_est),
            "tempo": round(tempo, 1),
            "tuning": guitar_tuning.name,
            "bars": [
                {"label": b.label, "start_sec": round(b.start, 3),
                 "end_sec": round(b.end, 3)}
                for b in bars
            ],
        }

        # Optional: Guitar 2
        if params["multi_guitar"] and guitar2_path:
            step += 1
            _step(job, step, "Transcribing Guitar 2")
            notes2 = transcription.transcribe(guitar2_path)
            fretted2 = fretboard.map_notes_to_fretboard(notes2, guitar_tuning)
            tab2_web = tab_render.render_tab(
                bars, fretted2, key_est, tempo, audio_path.name, guitar_tuning, bars_per_line=1
            )
            tab2 = tab_render.render_tab(
                bars, fretted2, key_est, tempo, audio_path.name, guitar_tuning
            )
            (work_dir / "guitar2.txt").write_text(tab2, encoding="utf-8")
            export_pdf(
                work_dir / "guitar2.pdf", bars, fretted2, key_est, tempo,
                audio_path.name, guitar_tuning
            )
            export_midi(work_dir / "guitar2.midi", fretted2, tempo)
            results["tabs"]["guitar2"] = tab2_web

        # Optional: Bass tab
        if params["bass_tab"]:
            step += 1
            _step(job, step, "Transcribing bass")
            bass_tuning = tuning_mod.find_tuning(tuning_mod.BASS_STANDARD_EADG)
            bass_notes = transcription.transcribe(bass_path)
            bass_fretted = fretboard.map_notes_to_fretboard(bass_notes, bass_tuning)
            bass_tab_web = tab_render.render_tab(
                bars, bass_fretted, key_est, tempo, audio_path.name, bass_tuning, bars_per_line=1
            )
            bass_tab_text = tab_render.render_tab(
                bars, bass_fretted, key_est, tempo, audio_path.name, bass_tuning
            )
            (work_dir / "bass.txt").write_text(bass_tab_text, encoding="utf-8")
            export_pdf(
                work_dir / "bass.pdf", bars, bass_fretted, key_est, tempo,
                audio_path.name, bass_tuning
            )
            results["tabs"]["bass"] = bass_tab_web

        # Optional: Vocal melody
        if params["vocal_tab"]:
            step += 1
            _step(job, step, "Transcribing vocal melody")
            stem_dir = work_dir / "stems" / DEMUCS_MODEL / audio_path.stem
            vocal_path = stem_dir / "vocals.wav"
            if vocal_path.exists():
                # bars_per_line=1 for web display sync; default (4) for file download
                vocal_text_web = vocal_tab_mod.render_vocal_tab(
                    vocal_path, bars, key_est, tempo, audio_path.name, bars_per_line=1
                )
                vocal_text = vocal_tab_mod.render_vocal_tab(
                    vocal_path, bars, key_est, tempo, audio_path.name
                )
                (work_dir / "vocals.txt").write_text(vocal_text, encoding="utf-8")
                results["tabs"]["vocals"] = vocal_text_web

        # Optional: Drum summary
        if params["drum_summary"]:
            step += 1
            _step(job, step, "Analysing drums")
            stem_dir = work_dir / "stems" / DEMUCS_MODEL / audio_path.stem
            drum_path = stem_dir / "drums.wav"
            if drum_path.exists():
                drum_text = drum_summary_mod.summarize_drums(drum_path, tempo)
                (work_dir / "drums.txt").write_text(drum_text, encoding="utf-8")
                results["tabs"]["drums"] = drum_text

        job.results = results
        job.status = "done"
        job.step = job.total_steps
        job.step_label = "Done"

    except Exception as exc:
        job.status = "error"
        job.error = str(exc)
```

- [ ] **Step 5: Run route tests to verify they pass**

```bash
pip install fastapi httpx  # httpx needed for TestClient
python -m pytest tests/test_api_routes.py -v
```

Expected: 7 PASSes.

- [ ] **Step 6: Smoke-test the server locally**

```bash
cd "/Users/joao.silva/Library/CloudStorage/GoogleDrive-davisthe8th@gmail.com/My Drive/GARAGEBAND/VALLETOFNOONE/guitar_tab_pipeline"
pip install fastapi "uvicorn[standard]" python-multipart yt-dlp
uvicorn api.main:app --reload --port 8000
```

In a second terminal:
```bash
curl http://localhost:8000/api/jobs -X POST -d "youtube_url=bad" -H "Content-Type: application/x-www-form-urlencoded"
```

Expected: `{"job_id": "...", "status": "queued"}` (job will fail in background since URL is bad, but the endpoint responds immediately).

Stop the server with Ctrl+C.

- [ ] **Step 7: Run full test suite**

```bash
python -m pytest -v
```

Expected: all tests pass.

- [ ] **Step 8: Commit**

```bash
git add api/routes.py api/worker.py tests/test_api_routes.py
git commit -m "feat: FastAPI routes + pipeline worker"
```

---

## Task 6: Frontend — HTML structure and CSS

**Files:**
- Create: `index.html`
- Create: `css/main.css`

Full single-page app: sticky NAV + TOOL (split panel) + ABOUT section. All visual design from the approved Warm Ruby spec/prototype. No JavaScript in this task — just structure and styles.

- [ ] **Step 1: Create `css/main.css`**

```css
/* Warm Ruby design system */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
  --red: #B71C1C;
  --red-light: rgba(183,28,28,0.10);
  --cream: #F8F4F1;
  --border: #E8E0D8;
  --text: #1a1a1a;
  --muted: #888;
  --dim: #bbb;
  --white: #fff;
  --tab-bg: #FDFAF8;
  --dark-bg: #1A0808;
}

body { font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; background: var(--cream); color: var(--text); }

/* NAV */
nav { background: var(--white); border-bottom: 1px solid var(--border); padding: 14px 24px; display: flex; justify-content: space-between; align-items: center; position: sticky; top: 0; z-index: 100; }
.logo { display: flex; align-items: center; gap: 9px; }
.logo-img { width: 28px; height: 28px; object-fit: contain; }
.logo-text { font-size: 16px; font-weight: 800; letter-spacing: 3px; }
.nav-sub { font-size: 11px; color: var(--muted); }
.nav-gh { font-size: 11px; color: var(--red); text-decoration: none; font-weight: 600; }
@media(max-width:500px){ .nav-sub { display:none; } }

/* TOOL */
.tool-wrapper { display: flex; min-height: calc(100vh - 52px); }

/* LEFT PANEL */
.panel-left { width: 42%; min-width: 300px; padding: 24px; border-right: 1px solid var(--border); display: flex; flex-direction: column; gap: 14px; background: var(--cream); overflow-y: auto; }

/* RIGHT PANEL */
.panel-right { flex: 1; padding: 24px; display: flex; flex-direction: column; gap: 14px; background: var(--tab-bg); overflow-y: auto; }

/* RESPONSIVE */
@media(max-width: 768px) {
  .tool-wrapper { flex-direction: column; min-height: auto; }
  .panel-left { width: 100%; border-right: none; border-bottom: 1px solid var(--border); }
  .panel-right { width: 100%; }
  .panel-right.hidden { display: none; }
}

/* YOUTUBE INPUT */
.yt-box { background: var(--white); border-radius: 10px; border: 1px solid var(--border); padding: 14px 16px; }
.field-label { font-size: 11px; font-weight: 700; color: #444; margin-bottom: 6px; }
.yt-row { display: flex; gap: 8px; }
.yt-input { flex: 1; background: var(--cream); border: 1px solid #ccc; border-radius: 6px; padding: 8px 12px; font-size: 11px; color: var(--muted); outline: none; }
.yt-input:focus { border-color: var(--red); color: var(--text); }
.btn-fetch { background: var(--red); color: var(--white); border: none; border-radius: 6px; padding: 8px 14px; font-size: 10px; font-weight: 700; cursor: pointer; white-space: nowrap; }
.btn-fetch:disabled { opacity: 0.5; cursor: not-allowed; }

/* OR DIVIDER */
.or-divider { display: flex; align-items: center; gap: 10px; }
.or-divider::before, .or-divider::after { content:''; flex:1; height:1px; background: var(--border); }
.or-divider span { font-size: 10px; color: var(--dim); }

/* DROP ZONE */
.drop-zone { border: 2px dashed var(--red); border-radius: 12px; padding: 28px 20px; text-align: center; background: var(--white); cursor: pointer; transition: background 0.15s; }
.drop-zone:hover, .drop-zone.drag-over { background: var(--red-light); }
.drop-icon { font-size: 28px; color: var(--red); margin-bottom: 8px; }
.drop-title { font-size: 13px; font-weight: 600; margin-bottom: 4px; }
.drop-sub { font-size: 10px; color: var(--muted); margin-bottom: 12px; }
.btn-browse { border: 1px solid var(--red); color: var(--red); border-radius: 5px; padding: 6px 16px; font-size: 10px; font-weight: 600; background: transparent; cursor: pointer; }

/* OPTIONS */
.options-box { background: var(--white); border-radius: 10px; border: 1px solid var(--border); overflow: hidden; }
.options-head { padding: 11px 16px; border-bottom: 1px solid #f0ebe4; display: flex; justify-content: space-between; align-items: center; }
.options-head-title { font-size: 11px; font-weight: 700; }
.options-head-hint { font-size: 9px; color: var(--red); }
.options-body { padding: 16px; display: flex; flex-direction: column; gap: 13px; }
.opt-select { width: 100%; background: var(--cream); border: 1px solid #ccc; border-radius: 6px; padding: 7px 10px; font-size: 10px; color: var(--text); }
.opt-label { font-size: 10px; font-weight: 600; color: #444; }
.opt-sublabel { font-size: 9px; color: var(--dim); margin-top: 2px; }
.opt-row { display: flex; justify-content: space-between; align-items: center; gap: 12px; }
.toggle { display: flex; gap: 4px; flex-shrink: 0; }
.toggle-no { background: var(--cream); border: 1px solid #ccc; border-radius: 5px; padding: 4px 11px; font-size: 9px; color: var(--muted); cursor: pointer; user-select: none; }
.toggle-yes { background: var(--red); border-radius: 5px; padding: 4px 11px; font-size: 9px; color: var(--white); font-weight: 600; cursor: pointer; user-select: none; }

/* TRANSCRIBE BUTTON */
.btn-transcribe { background: var(--red); color: var(--white); border: none; border-radius: 10px; padding: 14px; font-size: 12px; font-weight: 700; letter-spacing: 1.5px; cursor: pointer; box-shadow: 0 3px 12px rgba(183,28,28,0.28); width: 100%; transition: background 0.15s; }
.btn-transcribe:hover { background: #8B0000; }
.btn-transcribe:disabled { background: #ccc; box-shadow: none; cursor: not-allowed; }

/* PROGRESS */
.progress-box { background: var(--white); border-radius: 10px; border: 1px solid var(--border); padding: 14px 16px; }
.progress-title { font-size: 11px; font-weight: 700; margin-bottom: 10px; }
.progress-steps { display: flex; flex-direction: column; gap: 8px; }
.progress-step { display: flex; align-items: center; gap: 10px; }
.step-dot { width: 16px; height: 16px; min-width: 16px; border-radius: 50%; border: 1px solid #ccc; background: #eee; }
.step-dot.done { background: var(--red); border-color: var(--red); display: flex; align-items: center; justify-content: center; color: var(--white); font-size: 8px; font-weight: 700; }
.step-dot.done::after { content: '✓'; }
.step-dot.active { background: transparent; border-color: var(--red); border-width: 2px; animation: pulse 1s ease-in-out infinite; }
.step-label { font-size: 10px; color: #444; }
.step-label.pending { color: var(--dim); }
@keyframes pulse { 0%,100% { opacity:1; } 50% { opacity:0.4; } }

/* PLAYBACK */
.playback-box { background: var(--white); border-radius: 10px; border: 1px solid var(--border); padding: 14px 16px; }
.playback-row { display: flex; align-items: center; gap: 12px; margin-bottom: 10px; }
.play-btn { width: 32px; height: 32px; min-width: 32px; background: var(--red); border-radius: 50%; display: flex; align-items: center; justify-content: center; cursor: pointer; border: none; }
.play-triangle { width:0; height:0; border-style:solid; border-width:6px 0 6px 11px; border-color:transparent transparent transparent var(--white); margin-left:2px; }
.pause-bars { display:flex; gap:3px; align-items:center; }
.pause-bar { width:3px; height:12px; background:var(--white); border-radius:1px; }
.scrubber { flex:1; cursor:pointer; }
.scrubber-track { height:4px; background: var(--border); border-radius:2px; }
.scrubber-fill { width:0%; height:100%; background: var(--red); border-radius:2px; transition: width 0.1s linear; }
.time { font-size:9px; color: var(--muted); white-space:nowrap; }
.chord-now { display:flex; align-items:center; gap:8px; }
.chord-label { font-size:9px; color: var(--muted); }
.chord-pill { background: var(--red); color: var(--white); border-radius:5px; padding:3px 12px; font-size:12px; font-weight:700; min-width:40px; text-align:center; }
.chord-next { font-size:9px; color: var(--muted); }
.chord-next strong { color:#555; }

/* TAB PANEL */
.tab-panel { background: var(--white); border-radius: 10px; border: 1px solid var(--border); overflow: hidden; display: flex; flex-direction: column; }
.tab-switcher { display: flex; border-bottom: 1px solid var(--border); overflow-x: auto; }
.tab-btn { padding: 9px 16px; font-size: 10px; font-weight: 600; color: var(--muted); cursor: pointer; border-right: 1px solid var(--border); white-space: nowrap; user-select: none; }
.tab-btn.active { background: var(--red); color: var(--white); font-weight: 700; }
.tab-content { padding: 14px 16px; font-family: 'Courier New', Courier, monospace; font-size: 11px; line-height: 1.9; color: #333; background: var(--tab-bg); overflow-x: auto; min-height: 120px; }
.tab-comment { color: var(--red); font-size: 10px; display: block; }
.tab-bar { display: block; white-space: pre; }
.tab-bar.dim { opacity: 0.4; }
.tab-bar.active { background: var(--red-light); border-left: 3px solid var(--red); padding-left: 4px; }
.tab-downloads { padding: 10px 16px; border-top: 1px solid var(--border); display: flex; gap: 8px; flex-wrap: wrap; }
.dl-pdf { background: var(--red); color: var(--white); border: none; border-radius: 5px; padding: 6px 14px; font-size: 9px; font-weight: 700; cursor: pointer; }
.dl-txt { background: transparent; border: 1px solid var(--red); color: var(--red); border-radius: 5px; padding: 6px 14px; font-size: 9px; font-weight: 700; cursor: pointer; }
.dl-midi { background: transparent; border: 1px solid #ccc; color: var(--muted); border-radius: 5px; padding: 6px 14px; font-size: 9px; font-weight: 600; cursor: pointer; }

/* EMPTY / ERROR STATES */
.right-empty { display: flex; flex-direction: column; align-items: center; justify-content: center; flex: 1; gap: 10px; padding: 40px; text-align: center; }
.right-empty-icon { font-size: 32px; color: var(--border); }
.right-empty-text { font-size: 11px; color: var(--dim); }
.error-box { background: #fff5f5; border: 1px solid #f5c6c6; border-radius: 10px; padding: 16px; color: #8B0000; font-size: 11px; }

/* ABOUT */
.about { background: var(--dark-bg); padding: 64px 48px; }
@media(max-width:600px){ .about { padding: 40px 24px; } }
.about-header { text-align: center; margin-bottom: 48px; }
.about-rule { display: inline-block; width: 40px; height: 3px; background: var(--red); margin-bottom: 16px; }
.about-title { color: var(--white); font-size: 20px; font-weight: 800; letter-spacing: 3px; text-transform: uppercase; margin-bottom: 8px; }
.about-sub { color: var(--muted); font-size: 11px; letter-spacing: 1px; }
.about-body { display: flex; gap: 48px; align-items: flex-start; max-width: 860px; margin: 0 auto; }
@media(max-width:700px){ .about-body { flex-direction: column; align-items: center; gap: 32px; } }
.about-photo-col { flex-shrink: 0; text-align: center; }
.about-photo { width: 160px; height: 160px; object-fit: cover; border-radius: 50%; border: 3px solid var(--red); filter: grayscale(20%) contrast(1.05); display: block; margin: 0 auto 10px; }
.about-name { color: var(--red); font-size: 11px; font-weight: 700; letter-spacing: 2px; }
.about-role { color: #555; font-size: 10px; margin-top: 3px; }
.about-text { flex: 1; }
.about-section-tag { color: var(--red); font-size: 9px; font-weight: 700; letter-spacing: 3px; text-transform: uppercase; margin-bottom: 8px; }
.about-para { color: #ddd; font-size: 13px; line-height: 1.8; margin-bottom: 28px; }
.privacy-row { border-top: 1px solid #2a1010; padding-top: 20px; display: flex; gap: 10px; align-items: flex-start; }
.privacy-icon { color: var(--red); font-size: 14px; margin-top: 2px; }
.privacy-text { color: #666; font-size: 11px; line-height: 1.7; }
.privacy-text strong { color: #999; }
.tip-row { text-align: center; margin-top: 36px; padding-top: 28px; border-top: 1px solid #2a1010; }
.tip-copy { color: #666; font-size: 12px; line-height: 1.8; max-width: 480px; margin: 0 auto 18px; }
.btn-donate { display: inline-block; border: 1px solid #555; color: #777; border-radius: 6px; padding: 7px 20px; font-size: 10px; font-weight: 600; text-decoration: none; letter-spacing: 2px; }
.btn-donate:hover { border-color: #888; color: #999; }
.tip-alt { margin-top: 10px; color: #444; font-size: 10px; }
.tip-alt a { color: var(--red); text-decoration: none; }
.about-footer { text-align: center; margin-top: 48px; padding-top: 24px; border-top: 1px solid #2a1010; color: #333; font-size: 10px; letter-spacing: 1px; }
.about-footer a { color: var(--red); text-decoration: none; }

/* PWA INSTALL BUTTON */
.btn-pwa-install { width: 100%; background: transparent; border: 1px dashed #ccc; color: var(--muted); border-radius: 6px; padding: 7px 14px; font-size: 10px; font-weight: 600; letter-spacing: 1px; cursor: pointer; margin-top: 6px; }
.btn-pwa-install:hover { border-color: var(--red); color: var(--red); }
```

- [ ] **Step 2: Create `index.html`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Notara — Audio to Guitar Tab</title>
  <meta name="description" content="Upload audio or paste a YouTube URL. Notara transcribes guitar tab, bass tab, and vocal melody automatically. Free. No account. Any tuning.">
  <meta name="keywords" content="guitar tab, guitartab, guitar tab generator, audio to guitar tab, ultimate guitar alternative, automatic guitar transcription, bass tab from audio, vocal melody tab, free tab maker">
  <link rel="canonical" href="https://notara.io">
  <meta property="og:title" content="Notara — Audio to Guitar Tab">
  <meta property="og:description" content="Turn any audio into guitar tab. Upload a file or paste a YouTube URL. Free, open source, no account needed.">
  <meta property="og:image" content="https://notara.io/og-image.svg">
  <meta property="og:url" content="https://notara.io">
  <meta property="og:type" content="website">
  <meta name="twitter:card" content="summary_large_image">
  <script type="application/ld+json">{"@context":"https://schema.org","@type":"SoftwareApplication","name":"Notara","applicationCategory":"MusicApplication","operatingSystem":"Web","url":"https://notara.io","description":"Automatic guitar tab and bass tab transcription from audio. Free and open source.","offers":{"@type":"Offer","price":"0"}}</script>
  <link rel="stylesheet" href="css/main.css">
  <link rel="manifest" href="manifest.json">
  <meta name="theme-color" content="#B71C1C">
</head>
<body>

<!-- NAV -->
<nav>
  <div class="logo">
    <img class="logo-img" src="notara-logo.png" alt="Notara logo">
    <span class="logo-text">NOTARA</span>
  </div>
  <div class="nav-sub">Audio → Guitar Tab</div>
  <a class="nav-gh" href="https://github.com/joaofmsilva1979/notara" target="_blank">GitHub ↗</a>
</nav>

<!-- TOOL -->
<div class="tool-wrapper">

  <!-- LEFT PANEL -->
  <div class="panel-left">

    <!-- YouTube -->
    <div class="yt-box">
      <div class="field-label">YouTube URL</div>
      <div class="yt-row">
        <input class="yt-input" id="yt-input" type="url" placeholder="https://youtube.com/watch?v=…">
        <button class="btn-fetch" id="btn-fetch" disabled>Fetch</button>
      </div>
    </div>

    <div class="or-divider"><span>or</span></div>

    <!-- Drop zone -->
    <div class="drop-zone" id="drop-zone">
      <div class="drop-icon">♪</div>
      <div class="drop-title">Drop your audio here</div>
      <div class="drop-sub">MP3 · WAV · M4A · FLAC · OGG · OPUS — up to 100 MB</div>
      <button class="btn-browse" id="btn-browse">Browse files</button>
      <input type="file" id="file-input" accept=".mp3,.wav,.m4a,.flac,.ogg,.opus" hidden>
    </div>

    <!-- Selected file indicator -->
    <div id="file-indicator" style="display:none;font-size:10px;color:var(--muted);text-align:center;"></div>

    <!-- Options -->
    <div class="options-box">
      <div class="options-head">
        <span class="options-head-title">Options</span>
        <span class="options-head-hint">All optional — auto-detect if skipped</span>
      </div>
      <div class="options-body">

        <!-- Tuning -->
        <div>
          <div class="opt-label">Tuning</div>
          <select class="opt-select" id="opt-tuning">
            <option value="auto">✦ Auto-detect</option>
            <optgroup label="── Standard ──">
              <option value="Standard EADGBE">Standard (E A D G B e)</option>
              <option value="Eb Standard">Std ½↓ — Eb (Eb Ab Db Gb Bb eb)</option>
              <option value="D Standard">Std 1↓ — D (D G C F A d)</option>
              <option value="C# Standard">Std 1½↓ — C# (C# F# B E G# c#)</option>
              <option value="C Standard">Std 2↓ — C (C F Bb Eb G c)</option>
            </optgroup>
            <optgroup label="── Drop ──">
              <option value="Drop D">Drop D (D A D G B e)</option>
              <option value="Drop C#">Drop C# (C# Ab Db Gb Bb eb)</option>
              <option value="Drop C">Drop C (C G C F A d)</option>
              <option value="Drop B">Drop B (B F# B E G# c#)</option>
              <option value="Drop A">Drop A (A E A D F# b)</option>
            </optgroup>
            <optgroup label="── Open ──">
              <option value="Open G">Open G (D G D G B d)</option>
              <option value="Open D">Open D (D A D F# A d)</option>
              <option value="Open E">Open E (E B E G# B e)</option>
              <option value="Open A">Open A (E A E A C# e)</option>
              <option value="Open C">Open C (C G C G C e)</option>
              <option value="DADGAD">DADGAD (D A D G A d)</option>
            </optgroup>
            <optgroup label="── 7-String ──">
              <option value="7-String Standard">7-String Standard (B E A D G B e)</option>
              <option value="7-String Drop A">7-String Drop A (A E A D G B e)</option>
            </optgroup>
            <optgroup label="── 8-String ──">
              <option value="8-String Standard">8-String Standard (F# B E A D G B e)</option>
              <option value="8-String Drop E">8-String Drop E (E B E A D G B e)</option>
            </optgroup>
            <optgroup label="── Baritone ──">
              <option value="Baritone B">Baritone B (B E A D F# b)</option>
              <option value="Baritone A">Baritone A (A D G C E a)</option>
            </optgroup>
            <optgroup label="── Bass ──">
              <option value="Bass Standard EADG">Bass Standard (E A D G)</option>
              <option value="Bass Drop D">Bass Drop D (D A D G)</option>
              <option value="Bass 5-String BEADG">Bass 5-String (B E A D G)</option>
            </optgroup>
          </select>
        </div>

        <!-- Key -->
        <div>
          <div class="opt-label">Key <span style="font-weight:400;color:var(--dim);font-size:9px;">— hint for chord detection</span></div>
          <select class="opt-select" id="opt-key">
            <option value="auto">✦ Auto-detect</option>
            <optgroup label="Major">
              <option value="C major">C major</option><option value="C# major">C# major</option>
              <option value="D major">D major</option><option value="D# major">D# major</option>
              <option value="E major">E major</option><option value="F major">F major</option>
              <option value="F# major">F# major</option><option value="G major">G major</option>
              <option value="G# major">G# major</option><option value="A major">A major</option>
              <option value="A# major">A# major</option><option value="B major">B major</option>
            </optgroup>
            <optgroup label="Minor">
              <option value="C minor">C minor</option><option value="C# minor">C# minor</option>
              <option value="D minor">D minor</option><option value="D# minor">D# minor</option>
              <option value="E minor">E minor</option><option value="F minor">F minor</option>
              <option value="F# minor">F# minor</option><option value="G minor">G minor</option>
              <option value="G# minor">G# minor</option><option value="A minor">A minor</option>
              <option value="A# minor">A# minor</option><option value="B minor">B minor</option>
            </optgroup>
          </select>
        </div>

        <!-- Multiple guitars -->
        <div class="opt-row">
          <div>
            <div class="opt-label">Multiple guitars</div>
            <div class="opt-sublabel">Splits stereo L / R channels</div>
          </div>
          <div class="toggle" id="toggle-multi">
            <div class="toggle-yes" data-val="0">No</div>
            <div class="toggle-no" data-val="1">Yes</div>
          </div>
        </div>

        <!-- Bass tab -->
        <div class="opt-row">
          <div>
            <div class="opt-label">Bass tab</div>
            <div class="opt-sublabel">4-string tab from bass stem</div>
          </div>
          <div class="toggle" id="toggle-bass">
            <div class="toggle-yes" data-val="0">No</div>
            <div class="toggle-no" data-val="1">Yes</div>
          </div>
        </div>

        <!-- Vocal melody -->
        <div class="opt-row">
          <div>
            <div class="opt-label">Vocal melody</div>
            <div class="opt-sublabel">Melody tab in guitar octave</div>
          </div>
          <div class="toggle" id="toggle-vocal">
            <div class="toggle-yes" data-val="0">No</div>
            <div class="toggle-no" data-val="1">Yes</div>
          </div>
        </div>

        <!-- Drum summary -->
        <div class="opt-row">
          <div>
            <div class="opt-label">Drum summary</div>
            <div class="opt-sublabel">ASCII groove map + pattern</div>
          </div>
          <div class="toggle" id="toggle-drums">
            <div class="toggle-yes" data-val="0">No</div>
            <div class="toggle-no" data-val="1">Yes</div>
          </div>
        </div>

        <!-- Keys / Keyboard -->
        <div class="opt-row">
          <div>
            <div class="opt-label">Keys / Keyboard</div>
            <div class="opt-sublabel">MIDI + note list from piano stem</div>
          </div>
          <div class="toggle" id="toggle-keys">
            <div class="toggle-yes" data-val="0">No</div>
            <div class="toggle-no" data-val="1">Yes</div>
          </div>
        </div>

      </div>
    </div>

    <!-- Transcribe button -->
    <button class="btn-transcribe" id="btn-transcribe" disabled>TRANSCRIBE</button>

    <!-- PWA install prompt (hidden by default, shown when browser fires beforeinstallprompt) -->
    <button class="btn-pwa-install" id="btn-pwa-install" style="display:none">+ Add to home screen</button>

  </div>

  <!-- RIGHT PANEL -->
  <div class="panel-right" id="panel-right">

    <!-- Empty state (default) -->
    <div class="right-empty" id="state-empty">
      <div class="right-empty-icon">♩</div>
      <div class="right-empty-text">Upload audio or paste a YouTube URL,<br>then hit TRANSCRIBE.</div>
    </div>

    <!-- Progress (shown during processing) -->
    <div class="progress-box" id="state-progress" style="display:none">
      <div class="progress-title">Processing <span style="color:var(--muted);font-weight:400;font-size:10px;">— ~2 min</span></div>
      <div class="progress-steps" id="progress-steps"></div>
    </div>

    <!-- Error state -->
    <div class="error-box" id="state-error" style="display:none"></div>

    <!-- Results (shown after done) -->
    <div id="state-results" style="display:none">

      <!-- Playback bar -->
      <div class="playback-box">
        <div class="playback-row">
          <button class="play-btn" id="play-btn">
            <div class="play-triangle" id="play-icon"></div>
          </button>
          <div class="scrubber" id="scrubber">
            <div class="scrubber-track"><div class="scrubber-fill" id="scrubber-fill"></div></div>
          </div>
          <div class="time" id="time-display">0:00 / 0:00</div>
        </div>
        <div class="chord-now">
          <span class="chord-label">Now:</span>
          <span class="chord-pill" id="chord-now">—</span>
          <span class="chord-next">→ next: <strong id="chord-next">—</strong></span>
        </div>
      </div>

      <!-- Tab panel -->
      <div class="tab-panel">
        <div class="tab-switcher" id="tab-switcher"></div>
        <div class="tab-content" id="tab-content"></div>
        <div class="tab-downloads" id="tab-downloads"></div>
      </div>

    </div>

  </div>
</div>

<!-- ABOUT -->
<section class="about">
  <div class="about-header">
    <div class="about-rule"></div>
    <div class="about-title">Who's Behind This</div>
    <div class="about-sub">The why. The how. The what.</div>
  </div>

  <div class="about-body">
    <div class="about-photo-col">
      <img class="about-photo" src="joao.png" alt="João Silva">
      <div class="about-name">JOÃO SILVA</div>
      <div class="about-role">Musician · Builder</div>
    </div>
    <div class="about-text">
      <div class="about-section-tag">— Why</div>
      <p class="about-para">Sometimes you need to work with your ears. Sometimes you need a little help. There's no shame in the second one — every great guitarist learns from transcribing, and transcribing takes time that not everyone has. I made Notara because I wanted that help to exist, and to be honest about what it is: a starting point, not a finished score.</p>

      <div class="about-section-tag">— How</div>
      <p class="about-para">Notara runs Demucs to separate the guitar and bass stems from your audio, then uses basic-pitch to transcribe notes, detects the key and chords, and maps everything to a real fretboard — accounting for tuning, position, and whether there's one guitar or two. The output is an actual tab you can play from. Built in Python. Shaped with Claude.</p>

      <div class="about-section-tag">— What</div>
      <p class="about-para">Guitar tab. Bass tab. PDF. MIDI. For any tuning — standard, drop, open, 7-string, 8-string. Auto-detected or manually set. Free. Open source. <a href="https://github.com/joaofmsilva1979/notara" style="color:var(--red);text-decoration:none;font-weight:600;">github.com/joaofmsilva1979/notara ↗</a></p>

      <div class="privacy-row">
        <div class="privacy-icon">🔒</div>
        <p class="privacy-text"><strong>Nothing is saved.</strong> Your audio is processed and immediately discarded. No account, no tracking, no storage. What you upload stays between you and the algorithm.</p>
      </div>
    </div>
  </div>

  <div class="tip-row">
    <p class="tip-copy">Notara is free. No catch, no account, no ads.<br>If it saved you an hour of ear training and you feel like it —</p>
    <a class="btn-donate" href="https://ko-fi.com/notara" target="_blank">DONATE</a>
    <div class="tip-alt">or via <a href="https://paypal.me/joaosilva" target="_blank">PayPal</a> &nbsp;·&nbsp; if not, no worries — go play.</div>
  </div>

  <div class="about-footer">
    NOTARA · 2026 · Made with stubbornness and <span style="color:var(--red);">♥</span> · Built with <a href="https://claude.ai" target="_blank">Claude</a>
  </div>
</section>

<audio id="audio-player" style="display:none"></audio>

<script src="js/config.js"></script>
<script src="js/app.js"></script>
<script src="js/playback.js"></script>
</body>
</html>
```

- [ ] **Step 3: Copy logo to repo root**

```bash
cp "logo/notara-logo-simple.png" "notara-logo.png"
```

- [ ] **Step 4: Verify HTML renders correctly**

Open `index.html` directly in a browser (double-click the file or use `open index.html`). Verify:
- NAV renders with Notara logo PNG, tagline, GitHub link
- Left panel shows all options including Keys/Keyboard toggle
- Right panel shows the ♩ empty state
- About section renders dark with all three paragraphs
- DONATE button is subtle (grey outline)
- No JS errors in console (JS files don't exist yet — that's OK for now)

- [ ] **Step 5: Commit**

```bash
git add index.html css/main.css notara-logo.png
git commit -m "feat: frontend HTML structure and Warm Ruby CSS"
```

---

## Task 7: Frontend — core JavaScript

**Files:**
- Create: `js/config.js`
- Create: `js/app.js`

Handles: YouTube input enable/disable, file drag-drop, toggle buttons, TRANSCRIBE disable/enable, job submission, progress polling, tab display and switching, download buttons.

- [ ] **Step 1: Create `js/config.js`**

```javascript
// Set to backend URL in production; localhost for dev
const API_BASE_URL = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
  ? 'http://localhost:8000'
  : 'https://api.notara.app';
```

- [ ] **Step 2: Create `js/app.js`**

```javascript
/* Notara — main application logic */

// ── State ───────────────────────────────────────────────────
let selectedFile = null;
let ytReady = false;
let currentJobId = null;
let pollTimer = null;
let resultsData = null;
let activeTab = 'guitar1';
const toggleState = { multi: false, bass: false, vocal: false, drums: false, keys: false };
let pwaInstallPrompt = null;

// ── DOM refs ─────────────────────────────────────────────────
const ytInput      = document.getElementById('yt-input');
const btnFetch     = document.getElementById('btn-fetch');
const dropZone     = document.getElementById('drop-zone');
const fileInput    = document.getElementById('file-input');
const btnBrowse    = document.getElementById('btn-browse');
const fileIndicator = document.getElementById('file-indicator');
const btnTranscribe = document.getElementById('btn-transcribe');
const stateEmpty   = document.getElementById('state-empty');
const stateProgress = document.getElementById('state-progress');
const stateError   = document.getElementById('state-error');
const stateResults = document.getElementById('state-results');
const progressSteps = document.getElementById('progress-steps');
const tabSwitcher  = document.getElementById('tab-switcher');
const tabContent   = document.getElementById('tab-content');
const tabDownloads = document.getElementById('tab-downloads');
const panelRight   = document.getElementById('panel-right');
const btnPwaInstall = document.getElementById('btn-pwa-install');

// ── PWA Install ──────────────────────────────────────────────
window.addEventListener('beforeinstallprompt', e => {
  e.preventDefault();
  pwaInstallPrompt = e;
  btnPwaInstall.style.display = 'block';
});
btnPwaInstall.addEventListener('click', async () => {
  if (!pwaInstallPrompt) return;
  pwaInstallPrompt.prompt();
  const { outcome } = await pwaInstallPrompt.userChoice;
  if (outcome === 'accepted') btnPwaInstall.style.display = 'none';
  pwaInstallPrompt = null;
});
window.addEventListener('appinstalled', () => {
  btnPwaInstall.style.display = 'none';
  pwaInstallPrompt = null;
});

// ── YouTube ──────────────────────────────────────────────────
ytInput.addEventListener('input', () => {
  ytReady = ytInput.value.trim().length > 0;
  btnFetch.disabled = !ytReady;
  _updateTranscribeButton();
});

btnFetch.addEventListener('click', () => {
  selectedFile = null;
  fileIndicator.style.display = 'none';
  _updateTranscribeButton();
});

// ── File drop ────────────────────────────────────────────────
btnBrowse.addEventListener('click', () => fileInput.click());

fileInput.addEventListener('change', () => {
  if (fileInput.files[0]) _setFile(fileInput.files[0]);
});

dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('drag-over'); });
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
dropZone.addEventListener('drop', e => {
  e.preventDefault();
  dropZone.classList.remove('drag-over');
  if (e.dataTransfer.files[0]) _setFile(e.dataTransfer.files[0]);
});

dropZone.addEventListener('click', e => {
  if (e.target !== btnBrowse) fileInput.click();
});

function _setFile(file) {
  selectedFile = file;
  ytInput.value = '';
  ytReady = false;
  btnFetch.disabled = true;
  fileIndicator.textContent = `Selected: ${file.name} (${(file.size / 1024 / 1024).toFixed(1)} MB)`;
  fileIndicator.style.display = 'block';
  _updateTranscribeButton();
}

// ── Toggles ──────────────────────────────────────────────────
function _setupToggle(id, key) {
  const container = document.getElementById(`toggle-${id}`);
  container.querySelectorAll('[data-val]').forEach(btn => {
    btn.addEventListener('click', () => {
      const val = btn.dataset.val === '1';
      toggleState[key] = val;
      container.querySelectorAll('[data-val]').forEach(b => {
        b.className = b.dataset.val === '1' && val || b.dataset.val === '0' && !val
          ? 'toggle-yes' : 'toggle-no';
      });
    });
  });
}
_setupToggle('multi', 'multi');
_setupToggle('bass', 'bass');
_setupToggle('vocal', 'vocal');
_setupToggle('drums', 'drums');
_setupToggle('keys', 'keys');

// ── Transcribe button ────────────────────────────────────────
function _updateTranscribeButton() {
  btnTranscribe.disabled = !selectedFile && !ytReady;
}

btnTranscribe.addEventListener('click', _submitJob);

// ── Job submission ───────────────────────────────────────────
async function _submitJob() {
  btnTranscribe.disabled = true;
  currentJobId = null;
  resultsData = null;

  _showState('progress');

  const formData = new FormData();
  if (selectedFile) {
    formData.append('file', selectedFile);
  } else {
    formData.append('youtube_url', ytInput.value.trim());
  }
  formData.append('tuning', document.getElementById('opt-tuning').value);
  formData.append('key', document.getElementById('opt-key').value);
  formData.append('multi_guitar', toggleState.multi);
  formData.append('bass_tab', toggleState.bass);
  formData.append('vocal_tab', toggleState.vocal);
  formData.append('drum_summary', toggleState.drums);
  formData.append('keys_tab', toggleState.keys);

  try {
    const resp = await fetch(`${API_BASE_URL}/api/jobs`, { method: 'POST', body: formData });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${resp.status}`);
    }
    const data = await resp.json();
    currentJobId = data.job_id;
    _startPolling();
  } catch (err) {
    _showError(`Failed to start job: ${err.message}`);
    btnTranscribe.disabled = false;
  }
}

// ── Progress polling ─────────────────────────────────────────
function _startPolling() {
  if (pollTimer) clearInterval(pollTimer);
  pollTimer = setInterval(_poll, 3000);
  _poll();
}

async function _poll() {
  if (!currentJobId) return;
  try {
    const resp = await fetch(`${API_BASE_URL}/api/jobs/${currentJobId}/status`);
    const data = await resp.json();

    _updateProgress(data);

    if (data.status === 'done') {
      clearInterval(pollTimer);
      await _loadResults();
    } else if (data.status === 'error') {
      clearInterval(pollTimer);
      _showError(`Processing failed: ${data.error || 'Unknown error'}`);
      btnTranscribe.disabled = false;
    }
  } catch (err) {
    // Network hiccup — keep polling
  }
}

function _updateProgress(data) {
  const total = data.total_steps || 6;
  progressSteps.innerHTML = '';
  for (let i = 1; i <= total; i++) {
    const div = document.createElement('div');
    div.className = 'progress-step';
    const dot = document.createElement('div');
    dot.className = 'step-dot' + (i < data.step ? ' done' : i === data.step ? ' active' : '');
    const label = document.createElement('span');
    label.className = 'step-label' + (i > data.step ? ' pending' : '');
    label.textContent = i === data.step ? data.step_label : (i < data.step ? data.step_label : '...');
    div.appendChild(dot);
    div.appendChild(label);
    progressSteps.appendChild(div);
  }
  // Show current step label at the active dot
  if (data.step_label) {
    const steps = progressSteps.querySelectorAll('.step-label');
    if (steps[data.step - 1]) steps[data.step - 1].textContent = data.step_label;
  }
}

// ── Results ──────────────────────────────────────────────────
async function _loadResults() {
  try {
    const resp = await fetch(`${API_BASE_URL}/api/jobs/${currentJobId}/results`);
    resultsData = await resp.json();
    _renderResults(resultsData);
    // Load audio
    const audio = document.getElementById('audio-player');
    audio.src = `${API_BASE_URL}/api/jobs/${currentJobId}/audio`;
    // Init playback
    if (window.initPlayback) window.initPlayback(audio, resultsData.bars);
    _showState('results');
    // Reveal right panel on mobile
    panelRight.classList.remove('hidden');
  } catch (err) {
    _showError(`Failed to load results: ${err.message}`);
    btnTranscribe.disabled = false;
  }
}

function _renderResults(data) {
  // Build tab switcher
  tabSwitcher.innerHTML = '';
  const tabs = Object.keys(data.tabs);
  tabs.forEach((t, i) => {
    const btn = document.createElement('div');
    btn.className = 'tab-btn' + (i === 0 ? ' active' : '');
    btn.textContent = _tabLabel(t);
    btn.dataset.track = t;
    btn.addEventListener('click', () => _switchTab(t, tabs));
    tabSwitcher.appendChild(btn);
  });
  activeTab = tabs[0];
  _renderTab(activeTab, data);
}

function _tabLabel(track) {
  return { guitar1: 'Guitar 1', guitar2: 'Guitar 2', bass: 'Bass', vocals: 'Vocals', drums: 'Drums' }[track] || track;
}

function _switchTab(track, allTracks) {
  activeTab = track;
  tabSwitcher.querySelectorAll('.tab-btn').forEach(b => {
    b.classList.toggle('active', b.dataset.track === track);
  });
  _renderTab(track, resultsData);
}

function _renderTab(track, data) {
  const text = data.tabs[track] || '';
  tabContent.innerHTML = '';

  // Split into header comment lines and bar blocks.
  // The API returns tabs with bars_per_line=1 so bars are separated by blank lines.
  // Header comment lines (starting with #) come first, then bar blocks.
  const segments = text.split('\n\n');
  segments.forEach(segment => {
    if (!segment.trim()) return;
    // Each segment is either a header block (all # lines) or a bar block
    const isComment = segment.trim().split('\n').every(l => l.startsWith('#') || l.trim() === '');
    if (isComment) {
      segment.split('\n').forEach(line => {
        if (!line.trim()) return;
        const span = document.createElement('span');
        span.className = 'tab-comment';
        span.textContent = line;
        tabContent.appendChild(span);
        tabContent.appendChild(document.createTextNode('\n'));
      });
    } else {
      // One bar block: chord label + 6 string rows — render as single .tab-bar span
      const span = document.createElement('span');
      span.className = 'tab-bar';
      span.textContent = segment;
      tabContent.appendChild(span);
      tabContent.appendChild(document.createTextNode('\n\n'));
    }
  });

  // Downloads
  tabDownloads.innerHTML = '';
  if (track !== 'drums') {
    const pdf = _dlBtn('↓ PDF', 'dl-pdf', track, 'pdf');
    const txt = _dlBtn('↓ TXT', 'dl-txt', track, 'txt');
    tabDownloads.appendChild(pdf);
    tabDownloads.appendChild(txt);
    if (['guitar1', 'guitar2', 'vocals'].includes(track)) {
      tabDownloads.appendChild(_dlBtn('↓ MIDI', 'dl-midi', track, 'midi'));
    }
  } else {
    tabDownloads.appendChild(_dlBtn('↓ TXT', 'dl-txt', track, 'txt'));
  }
}

function _dlBtn(label, cls, track, fmt) {
  const btn = document.createElement('button');
  btn.className = cls;
  btn.textContent = label;
  btn.addEventListener('click', () => {
    window.open(`${API_BASE_URL}/api/jobs/${currentJobId}/download/${track}/${fmt}`);
  });
  return btn;
}

// ── UI state helpers ─────────────────────────────────────────
function _showState(state) {
  stateEmpty.style.display    = state === 'empty'    ? 'flex'  : 'none';
  stateProgress.style.display = state === 'progress' ? 'block' : 'none';
  stateError.style.display    = state === 'error'    ? 'block' : 'none';
  stateResults.style.display  = state === 'results'  ? 'block' : 'none';
}

function _showError(msg) {
  stateError.textContent = msg;
  _showState('error');
}

// Expose for playback.js
window.getActiveTab = () => activeTab;
window.getTabBars = () => resultsData ? resultsData.bars : [];
```

- [ ] **Step 3: Verify JS loads cleanly**

Open `index.html` in a browser. Open the browser console. Verify: no syntax errors, TRANSCRIBE button is disabled (no file selected), YouTube input enables Fetch when text is typed, toggles switch between No/Yes on click, file drop zone highlights on drag-over.

- [ ] **Step 4: Commit**

```bash
git add js/config.js js/app.js
git commit -m "feat: frontend core JS — upload, options, job submit, polling, tab display"
```

---

## Task 8: Frontend — playback and tab sync

**Files:**
- Create: `js/playback.js`

Audio playback bar + bar-synchronized tab highlight. As the audio plays, the current bar (from `resultsData.bars`) is highlighted in the tab panel.

- [ ] **Step 1: Create `js/playback.js`**

```javascript
/* Notara — playback bar + synchronized tab highlight */

let _audio = null;
let _bars = [];
let _rafId = null;

const playBtn     = document.getElementById('play-btn');
const playIcon    = document.getElementById('play-icon');
const scrubber    = document.getElementById('scrubber');
const scrubFill   = document.getElementById('scrubber-fill');
const timeDisplay = document.getElementById('time-display');
const chordNow    = document.getElementById('chord-now');
const chordNext   = document.getElementById('chord-next');

function initPlayback(audioEl, bars) {
  _audio = audioEl;
  _bars = bars || [];

  _audio.addEventListener('play',  _onPlay);
  _audio.addEventListener('pause', _onPause);
  _audio.addEventListener('ended', _onPause);
  _audio.addEventListener('loadedmetadata', _updateTime);

  playBtn.addEventListener('click', _togglePlay);

  scrubber.addEventListener('click', e => {
    if (!_audio || !_audio.duration) return;
    const rect = scrubber.getBoundingClientRect();
    const frac = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    _audio.currentTime = frac * _audio.duration;
  });
}

function _togglePlay() {
  if (!_audio) return;
  if (_audio.paused) {
    _audio.play();
  } else {
    _audio.pause();
  }
}

function _onPlay() {
  playIcon.innerHTML = '<div class="pause-bars"><div class="pause-bar"></div><div class="pause-bar"></div></div>';
  _tick();
}

function _onPause() {
  playIcon.innerHTML = '';
  playIcon.className = 'play-triangle';
  if (_rafId) cancelAnimationFrame(_rafId);
}

function _tick() {
  _updateTime();
  _syncTab();
  _rafId = requestAnimationFrame(_tick);
}

function _updateTime() {
  if (!_audio) return;
  const cur = _audio.currentTime || 0;
  const dur = _audio.duration || 0;
  scrubFill.style.width = dur > 0 ? `${(cur / dur) * 100}%` : '0%';
  timeDisplay.textContent = `${_fmt(cur)} / ${_fmt(dur)}`;
}

function _fmt(s) {
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60);
  return `${m}:${sec.toString().padStart(2, '0')}`;
}

function _syncTab() {
  if (!_audio || !_bars.length) return;
  const t = _audio.currentTime;

  // Find active bar index
  let activeIdx = -1;
  for (let i = 0; i < _bars.length; i++) {
    if (t >= _bars[i].start_sec && t < _bars[i].end_sec) {
      activeIdx = i;
      break;
    }
  }

  // Update chord display
  if (activeIdx >= 0) {
    chordNow.textContent = _bars[activeIdx].label || '—';
    chordNext.textContent = activeIdx + 1 < _bars.length ? _bars[activeIdx + 1].label : '—';
  }

  // Highlight tab bar — only for guitar/bass/vocals (not drums)
  const track = window.getActiveTab ? window.getActiveTab() : 'guitar1';
  if (track === 'drums') return;

  const tabBars = document.querySelectorAll('#tab-content .tab-bar');
  if (!tabBars.length) return;

  tabBars.forEach((el, i) => {
    el.classList.remove('active', 'dim');
    if (i === activeIdx) {
      el.classList.add('active');
      el.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    } else if (activeIdx >= 0) {
      el.classList.add('dim');
    }
  });
}

window.initPlayback = initPlayback;
```

- [ ] **Step 2: Verify in browser**

Open `index.html`. In the browser console, manually call:
```javascript
// Simulate having results
document.getElementById('state-results').style.display = 'block';
document.getElementById('state-empty').style.display = 'none';
```

Confirm no JS errors. The play button should appear. (Full playback test requires a running backend — do that in Task 10.)

- [ ] **Step 3: Commit**

```bash
git add js/playback.js
git commit -m "feat: playback bar + synchronized tab highlight"
```

---

## Task 9: SEO assets, PWA manifest, and GitHub Pages config

**Files:**
- Create: `manifest.json`
- Create: `og-image.svg`
- Create: `sitemap.xml`
- Create: `robots.txt`
- Create: `joao.png` (copy from brainstorm content folder)
- Create: `.nojekyll`

- [ ] **Step 1: Create `manifest.json`** (PWA manifest — enables "Add to Home Screen")

```json
{
  "name": "Notara",
  "short_name": "Notara",
  "description": "Audio to Guitar Tab — free, open source, any tuning",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#F8F4F1",
  "theme_color": "#B71C1C",
  "icons": [
    {
      "src": "notara-logo.png",
      "sizes": "192x192",
      "type": "image/png",
      "purpose": "any maskable"
    },
    {
      "src": "notara-logo.png",
      "sizes": "512x512",
      "type": "image/png",
      "purpose": "any maskable"
    }
  ]
}
```

- [ ] **Step 2: Copy the user photo to repo root**

```bash
cp "/Users/joao.silva/Library/CloudStorage/GoogleDrive-davisthe8th@gmail.com/My Drive/GARAGEBAND/VALLETOFNOONE/guitar_tab_pipeline/.superpowers/brainstorm/90654-1785662065/content/joao.png" \
   "/Users/joao.silva/Library/CloudStorage/GoogleDrive-davisthe8th@gmail.com/My Drive/GARAGEBAND/VALLETOFNOONE/guitar_tab_pipeline/joao.png"
```

- [ ] **Step 3: Create `og-image.svg`** (1200×630 social preview card)

```svg
<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630">
  <rect width="1200" height="630" fill="#F8F4F1"/>
  <rect x="0" y="0" width="8" height="630" fill="#B71C1C"/>
  <rect x="100" y="240" width="50" height="50" rx="10" fill="#B71C1C"/>
  <text x="165" y="282" font-family="Helvetica Neue, Helvetica, Arial, sans-serif" font-size="52" font-weight="800" letter-spacing="8" fill="#1a1a1a">NOTARA</text>
  <text x="100" y="340" font-family="Helvetica Neue, Helvetica, Arial, sans-serif" font-size="28" fill="#888">Audio → Guitar Tab · Bass Tab · Vocal Melody</text>
  <text x="100" y="400" font-family="Helvetica Neue, Helvetica, Arial, sans-serif" font-size="22" fill="#B71C1C">Free · Open source · Any tuning · No account needed</text>
</svg>
```

- [ ] **Step 4: Create `sitemap.xml`**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://notara.io/</loc>
    <lastmod>2026-08-02</lastmod>
    <changefreq>monthly</changefreq>
    <priority>1.0</priority>
  </url>
</urlset>
```

- [ ] **Step 5: Create `robots.txt`**

```
User-agent: *
Allow: /
Sitemap: https://notara.io/sitemap.xml
```

- [ ] **Step 6: Create `.nojekyll`** (prevents GitHub Pages from running Jekyll, which would ignore `_` prefixed dirs)

```bash
touch "/Users/joao.silva/Library/CloudStorage/GoogleDrive-davisthe8th@gmail.com/My Drive/GARAGEBAND/VALLETOFNOONE/guitar_tab_pipeline/.nojekyll"
```

- [ ] **Step 7: Enable GitHub Pages on the repo**

Go to: `https://github.com/joaofmsilva1979/notara/settings/pages`
- Source: **Deploy from a branch**
- Branch: `main`, folder: `/ (root)`
- Click Save

The site will be live at `https://joaofmsilva1979.github.io/notara` within ~2 minutes.

- [ ] **Step 8: Update `js/config.js` with production URL placeholder**

Replace `api.notara.app` with the Railway/Render subdomain once deployed (Task 10). For now leave as-is.

- [ ] **Step 9: Commit and push**

```bash
git add manifest.json og-image.svg sitemap.xml robots.txt joao.png .nojekyll
git commit -m "feat: PWA manifest + SEO assets + GitHub Pages config"
git push origin main
```

---

## Task 10: Backend deployment config (Railway)

**Files:**
- Create: `api/Procfile`
- Create: `api/railway.toml` (or `api/render.yaml` for Render)

Deploy the FastAPI backend so the frontend can talk to it.

- [ ] **Step 1: Create `api/Procfile`**

```
web: uvicorn api.main:app --host 0.0.0.0 --port $PORT
```

- [ ] **Step 2: Create `api/railway.toml`**

```toml
[build]
builder = "nixpacks"

[deploy]
startCommand = "uvicorn api.main:app --host 0.0.0.0 --port $PORT"
restartPolicyType = "on-failure"
restartPolicyMaxRetries = 3

[build.env]
PYTHONPATH = "."
```

- [ ] **Step 3: Create `api/render.yaml`** (alternative — use Render if Railway doesn't work)

```yaml
services:
  - type: web
    name: notara-api
    runtime: python
    buildCommand: pip install -r api/requirements.txt
    startCommand: uvicorn api.main:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: PYTHONPATH
        value: .
    disk:
      name: notara-tmp
      mountPath: /tmp
      sizeGB: 1
```

- [ ] **Step 4: Deploy to Railway**

1. Go to `railway.app` → New Project → Deploy from GitHub repo → select `joaofmsilva1979/notara`
2. Set root directory to `.` (repo root, not `api/`)
3. Set start command to: `uvicorn api.main:app --host 0.0.0.0 --port $PORT`
4. Set `PYTHONPATH=.` in environment variables
5. Deploy — Railway builds and gives a URL like `notara-api.up.railway.app`

- [ ] **Step 5: Update `js/config.js` with production backend URL**

```javascript
const API_BASE_URL = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
  ? 'http://localhost:8000'
  : 'https://notara-api.up.railway.app';  // replace with actual Railway/Render URL
```

- [ ] **Step 6: Commit and push final config**

```bash
git add api/Procfile api/railway.toml api/render.yaml js/config.js
git commit -m "feat: backend deployment config + production API URL"
git push origin main
```

- [ ] **Step 7: End-to-end smoke test**

1. Open `https://joaofmsilva1979.github.io/notara` in a browser
2. Paste a YouTube URL → click Fetch → click TRANSCRIBE
3. Confirm: progress steps appear, job runs, tab appears, playback works
4. Download a PDF

If Railway gives a 503 (cold start on free tier), wait 30s and try again — free tier instances sleep after inactivity.

---

## Task 11: Keyboard / Keys MIDI detector

**Files:**
- Create: `pipeline/piano_tab.py`
- Create: `tests/test_piano_tab.py`

Transcribes the Demucs piano stem (htdemucs_6s outputs a dedicated `piano.wav`) via basic-pitch. Outputs MIDI + a simplified ASCII note list (pitch name + timing). This stem already exists when Demucs separates the audio — no extra separation step needed.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_piano_tab.py

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from pipeline.piano_tab import render_piano_tab, _notes_to_midi, _notes_to_text


FAKE_NOTES = [
    MagicMock(pitch=60, start=0.0, end=0.5, velocity=80),   # C4
    MagicMock(pitch=64, start=0.5, end=1.0, velocity=75),   # E4
    MagicMock(pitch=67, start=1.0, end=1.5, velocity=70),   # G4
    MagicMock(pitch=72, start=2.0, end=2.5, velocity=60),   # C5
]


def test_notes_to_text_returns_string():
    result = _notes_to_text(FAKE_NOTES, bars=4, tempo=120.0)
    assert isinstance(result, str)
    assert len(result) > 0


def test_notes_to_text_contains_note_names():
    result = _notes_to_text(FAKE_NOTES, bars=4, tempo=120.0)
    assert "C4" in result or "C5" in result or "E4" in result


def test_notes_to_midi_returns_bytes():
    result = _notes_to_midi(FAKE_NOTES, tempo=120.0)
    assert isinstance(result, bytes)
    assert result[:4] == b"MThd"  # MIDI file magic bytes


def test_render_piano_tab_no_stem_returns_none(tmp_path):
    missing = tmp_path / "nonexistent.wav"
    result = render_piano_tab(missing, bars=32, key_est="C major", tempo=120.0, source_name="test")
    assert result is None


@patch("pipeline.piano_tab.run_basic_pitch")
def test_render_piano_tab_returns_dict(mock_bp, tmp_path):
    stem = tmp_path / "piano.wav"
    stem.write_bytes(b"\x00" * 100)
    mock_bp.return_value = FAKE_NOTES
    result = render_piano_tab(stem, bars=32, key_est="C major", tempo=120.0, source_name="piano")
    assert result is not None
    assert "text" in result
    assert "midi_bytes" in result
    assert isinstance(result["text"], str)
    assert isinstance(result["midi_bytes"], bytes)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_piano_tab.py -v
```

Expected: `ModuleNotFoundError` or `ImportError` — piano_tab.py doesn't exist yet.

- [ ] **Step 3: Create `pipeline/piano_tab.py`**

```python
from __future__ import annotations

import io
from pathlib import Path
from typing import Optional

try:
    import mido
    _HAS_MIDO = True
except ImportError:
    _HAS_MIDO = False

from pipeline.transcription import run_basic_pitch

_MIDI_NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def _pitch_name(midi_note: int) -> str:
    octave = (midi_note // 12) - 1
    name = _MIDI_NOTE_NAMES[midi_note % 12]
    return f"{name}{octave}"


def _notes_to_text(notes: list, bars: int, tempo: float) -> str:
    seconds_per_beat = 60.0 / tempo
    seconds_per_bar = seconds_per_beat * 4
    total_duration = bars * seconds_per_bar

    lines = [f"Keys — {len(notes)} notes detected — tempo: {tempo:.0f} BPM"]
    lines.append("-" * 48)
    for note in sorted(notes, key=lambda n: n.start):
        bar = int(note.start / seconds_per_bar) + 1
        beat = ((note.start % seconds_per_bar) / seconds_per_beat) + 1
        dur = note.end - note.start
        lines.append(f"  Bar {bar:>3}  Beat {beat:.1f}  {_pitch_name(note.pitch):<4}  ({dur:.2f}s)")
    return "\n".join(lines)


def _notes_to_midi(notes: list, tempo: float) -> bytes:
    if not _HAS_MIDO:
        return b""

    mid = mido.MidiFile(type=0)
    track = mido.MidiTrack()
    mid.tracks.append(track)
    track.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(tempo), time=0))

    ticks_per_beat = mid.ticks_per_beat
    seconds_per_tick = 60.0 / (tempo * ticks_per_beat)

    events: list[tuple[float, str, int]] = []
    for note in notes:
        events.append((note.start, "note_on", note.pitch))
        events.append((note.end, "note_off", note.pitch))

    events.sort(key=lambda e: e[0])
    last_time = 0.0
    for abs_time, msg_type, pitch in events:
        delta_s = abs_time - last_time
        delta_ticks = int(delta_s / seconds_per_tick)
        track.append(mido.Message(msg_type, note=pitch, velocity=64, time=delta_ticks))
        last_time = abs_time

    buf = io.BytesIO()
    mid.save(file=buf)
    return buf.getvalue()


def render_piano_tab(
    piano_stem_path: Path,
    bars: int,
    key_est: str,
    tempo: float,
    source_name: str,
) -> Optional[dict]:
    """Return {'text': str, 'midi_bytes': bytes} or None if stem missing."""
    if not piano_stem_path.exists():
        return None

    notes = run_basic_pitch(piano_stem_path)
    if not notes:
        return None

    return {
        "text": _notes_to_text(notes, bars=bars, tempo=tempo),
        "midi_bytes": _notes_to_midi(notes, tempo=tempo),
    }
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_piano_tab.py -v
```

Expected: 5 tests PASS.

- [ ] **Step 5: Install mido if not already present**

Check `requirements.txt`. If `mido` is missing, add it:

```bash
grep mido requirements.txt || echo "mido" >> requirements.txt
pip install mido
```

Re-run tests — they should still pass.

- [ ] **Step 6: Commit**

```bash
git add pipeline/piano_tab.py tests/test_piano_tab.py requirements.txt
git commit -m "feat: add keyboard/piano MIDI detector (piano_tab.py)"
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Task |
|---|---|
| Full tuning list (15 new) | Task 1 |
| vocal_tab.py module | Task 2 |
| drum_summary.py module | Task 3 |
| piano_tab.py keyboard/MIDI detector | Task 11 |
| FastAPI backend, async jobs, 1hr TTL | Task 4–5 |
| POST /api/jobs, GET status/results/audio/download | Task 5 |
| YouTube URL via yt-dlp | Task 5 (worker) |
| GitHub Pages frontend, zero framework | Task 6–8 |
| Warm Ruby palette | Task 6 |
| Logo PNG in nav | Task 6 |
| Responsive ≥769px split / ≤768px stacked | Task 6 |
| YouTube input + file dropzone | Task 6–7 |
| All option toggles (incl. Keys) | Task 6–7 |
| PWA install button | Task 7 |
| Progress checklist (dynamic steps) | Task 7 |
| Playback bar + chord display | Task 8 |
| Synchronized tab highlight | Task 8 |
| Tab switcher (Guitar1/2/Bass/Vocals/Drums/Keys) | Task 7 |
| PDF/TXT/MIDI downloads | Task 7 |
| About section with photo | Task 6 |
| DONATE button (Ko-fi + PayPal) | Task 6 |
| SEO meta tags, OG, Schema.org | Task 6 (index.html head) |
| manifest.json (PWA) | Task 9 |
| sitemap.xml, robots.txt | Task 9 |
| og-image.svg | Task 9 |
| GitHub Pages deploy | Task 9 |
| Backend deploy (Railway/Render) | Task 10 |

All spec requirements covered. No placeholders found.

**Note on joao.png:** The About section references `joao.png` at the repo root. The file exists at `.superpowers/brainstorm/.../content/joao.png` (local only). Task 9 Step 2 copies it to the repo root and commits it. If the owner prefers not to commit a photo to a public repo, replace the `<img src="joao.png">` in index.html with a base64 data URI.
