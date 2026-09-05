# Sprint 1+2 — Lyrics + BTC/SynthTab Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Commit the lyrics feature (backend already done), add fallback protection for BTC and SynthTab, write tests for both experimental wrappers, add a benchmark script, and verify the frontend changes.

**Architecture:** Backend lyrics integration and BTC/SynthTab integration already exist in `api/worker.py` and `api/routes.py` (unstaged). This plan hardens those integrations (fallback on exception), adds tests, benchmark script, and verifies the frontend changes before commiting the full feature set.

**Tech Stack:** Python 3.10+, pytest, unittest.mock, torch (mocked in tests), librosa, FastAPI.

---

## Environment note

All Python commands use the project virtualenv. Always invoke as:
```bash
cd ~/Library/CloudStorage/GoogleDrive-davisthe8th@gmail.com/My\ Drive/GARAGEBAND/VALLETOFNOONE/guitar_tab_pipeline
.venv/bin/python3 -m pytest ...
```
Never use bare `pytest` or `python3` — their shebangs are broken from a Google Drive folder rename.

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `api/worker.py` | Modify | Add try/except fallback around SynthTab and BTC calls |
| `tests/test_chord_detection_btc.py` | Create | Unit tests for BTC wrapper (mocked model) |
| `tests/test_transcription_synthtab.py` | Create | Unit tests for SynthTab wrapper (mocked model) |
| `tests/benchmark.py` | Create | CLI script: legacy vs BTC/SynthTab quality comparison |

---

### Task 1: Add fallback for SynthTab transcription in `api/worker.py`

**Files:**
- Modify: `api/worker.py` lines 107 and 194

Currently `worker.py` calls `transcription_synthtab.transcribe()` without error handling. If the SynthTab model is missing or crashes (CUDA OOM, corrupt weights), the entire job dies with a cryptic error. This task wraps both calls (Guitar 1 and Guitar 2) in try/except that falls back to `transcription.transcribe()`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_worker_fallback.py`:

```python
"""Test that worker.run_job falls back gracefully when SynthTab or BTC fail."""
from pathlib import Path
from unittest.mock import MagicMock, patch
import numpy as np
import pytest


def _make_job(tmp_path):
    job = MagicMock()
    job.work_dir = tmp_path
    job.total_steps = 10
    job.step = 0
    job.step_label = ""
    job.status = "queued"
    job.error = ""
    return job


def _librosa_mock():
    """MagicMock for the entire librosa import in api.worker.
    
    Patches load, effects.hpss, feature.chroma_cens, frames_to_time
    so worker.py's chroma computation doesn't touch real audio.
    """
    m = MagicMock()
    m.load.return_value = (np.zeros(22050), 22050)
    m.effects.hpss.return_value = (np.zeros(22050), np.zeros(22050))
    m.feature.chroma_cens.return_value = np.zeros((12, 10))
    m.frames_to_time.return_value = np.zeros(10)
    return m


_BASE_PARAMS = {
    "youtube_url": None,
    "tuning": "Standard EADGBE",
    "key": "auto",
    "multi_guitar": False,
    "bass_tab": False,
    "vocal_tab": False,
    "drum_summary": False,
    "keys_tab": False,
    "lyrics_raw": None,
}


def test_synthtab_failure_falls_back_to_basic_pitch(tmp_path):
    """When SynthTab raises, worker uses basic-pitch and job still completes."""
    from pipeline.transcription import Note
    from pipeline.chord_detection import ChordSegment

    fake_notes = [Note(start=0.0, end=0.5, pitch=60, velocity=0.8)]
    fake_bars = [ChordSegment(bar_index=0, start=0.0, end=2.0, label="Em")]

    with (
        patch("api.worker.job_store.get_job") as mock_get_job,
        patch("api.worker.separation.separate", return_value=(
            tmp_path / "harm.wav", tmp_path / "bass.wav", tmp_path / "guitar.wav"
        )),
        patch("api.worker.transcription_synthtab.transcribe",
              side_effect=RuntimeError("model missing")),
        patch("api.worker.transcription.transcribe", return_value=fake_notes),
        patch("api.worker.librosa", _librosa_mock()),
        patch("api.worker.key_detection.detect_key", return_value=MagicMock()),
        patch("api.worker.chord_detection.detect_chords",
              return_value=(fake_bars, 120.0)),
        patch("api.worker.chord_detection_btc.detect_chords_btc",
              return_value=(fake_bars, fake_bars)),
        patch("api.worker.fretboard.map_notes_to_fretboard", return_value=[]),
        patch("api.worker.tab_render.render_tab", return_value=""),
        patch("api.worker.export_pdf"),
        patch("api.worker.export_midi"),
        patch("api.worker.tuning_mod.find_tuning",
              return_value=MagicMock(name="Standard EADGBE")),
        patch("api.worker.tuning_mod.suggest_alternate_tuning", return_value=None),
    ):
        job = _make_job(tmp_path)
        mock_get_job.return_value = job

        from api import worker
        worker.run_job("test-job", {"audio_path": tmp_path / "audio.wav", **_BASE_PARAMS})

        assert job.status == "done"
        assert "fallback" in job.step_label.lower()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/bin/python3 -m pytest tests/test_worker_fallback.py -v
```
Expected: FAIL — `job.status` is `"error"` (no fallback yet) and `"fallback"` not in `step_label`.

- [ ] **Step 3: Add SynthTab fallback to `api/worker.py`**

Replace line 107 (Guitar 1 transcription):

```python
        # Step: Transcribe Guitar 1
        step += 1
        _step(job, step, "Transcribing Guitar 1")
        guitar_tuning_name = params["tuning"]
        if guitar_tuning_name in ("auto", "Standard EADGBE"):
            guitar_tuning = tuning_mod.find_tuning(tuning_mod.STANDARD_E_A_D_G_B_E)
        else:
            guitar_tuning = tuning_mod.find_tuning(guitar_tuning_name)
        try:
            notes1 = transcription_synthtab.transcribe(guitar1_path)
        except Exception as exc:
            job.step_label += f" [fallback basic-pitch: {type(exc).__name__}]"
            notes1 = transcription.transcribe(guitar1_path)
```

Replace line 194 (Guitar 2 transcription, inside `if params["multi_guitar"] and guitar2_path:`):

```python
            try:
                notes2 = transcription_synthtab.transcribe(guitar2_path)
            except Exception as exc:
                job.step_label += f" [fallback basic-pitch: {type(exc).__name__}]"
                notes2 = transcription.transcribe(guitar2_path)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
.venv/bin/python3 -m pytest tests/test_worker_fallback.py::test_synthtab_failure_falls_back_to_basic_pitch -v
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add api/worker.py tests/test_worker_fallback.py
git commit -m "feat: SynthTab fallback to basic-pitch on exception in worker"
```

---

### Task 2: Add fallback for BTC chord detection in `api/worker.py`

**Files:**
- Modify: `api/worker.py` lines 150-156
- Modify: `tests/test_worker_fallback.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_worker_fallback.py`:

```python
def test_btc_failure_falls_back_to_legacy_chords(tmp_path):
    """When BTC raises, worker uses legacy chord detection and job still completes."""
    from pipeline.transcription import Note
    from pipeline.chord_detection import ChordSegment

    fake_notes = [Note(start=0.0, end=0.5, pitch=60, velocity=0.8)]
    fake_bars = [ChordSegment(bar_index=0, start=0.0, end=2.0, label="Em")]

    with (
        patch("api.worker.job_store.get_job") as mock_get_job,
        patch("api.worker.separation.separate", return_value=(
            tmp_path / "harm.wav", tmp_path / "bass.wav", tmp_path / "guitar.wav"
        )),
        patch("api.worker.transcription_synthtab.transcribe", return_value=fake_notes),
        patch("api.worker.librosa", _librosa_mock()),
        patch("api.worker.key_detection.detect_key", return_value=MagicMock()),
        patch("api.worker.chord_detection.detect_chords",
              return_value=(fake_bars, 120.0)),
        patch("api.worker.chord_detection_btc.detect_chords_btc",
              side_effect=RuntimeError("GPU OOM")),
        patch("api.worker.fretboard.map_notes_to_fretboard", return_value=[]),
        patch("api.worker.tab_render.render_tab", return_value=""),
        patch("api.worker.export_pdf"),
        patch("api.worker.export_midi"),
        patch("api.worker.tuning_mod.find_tuning",
              return_value=MagicMock(name="Standard EADGBE")),
        patch("api.worker.tuning_mod.suggest_alternate_tuning", return_value=None),
    ):
        job = _make_job(tmp_path)
        mock_get_job.return_value = job

        from api import worker
        worker.run_job("test-job", {"audio_path": tmp_path / "audio.wav", **_BASE_PARAMS})

        assert job.status == "done"
        assert "fallback" in job.step_label.lower()
        assert job.results["bars"][0]["label"] == "Em"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/bin/python3 -m pytest tests/test_worker_fallback.py::test_btc_failure_falls_back_to_legacy_chords -v
```
Expected: FAIL — job status is `"error"`.

- [ ] **Step 3: Add BTC fallback to `api/worker.py`**

Wrap the BTC call (currently lines ~150-156) in try/except:

```python
        # BTC neural chord recognition on the FULL MIX
        bass_harmonic, _ = librosa.effects.hpss(bass_y)
        bass_chroma = librosa.feature.chroma_cens(y=bass_harmonic, sr=bass_sr)
        bass_chroma_times = librosa.frames_to_time(np.arange(bass_chroma.shape[1]), sr=bass_sr)
        guitar_harmonic, _ = librosa.effects.hpss(y_guitar)
        guitar_chroma = librosa.feature.chroma_cens(y=guitar_harmonic, sr=sr_guitar)
        guitar_chroma_times = librosa.frames_to_time(np.arange(guitar_chroma.shape[1]), sr=sr_guitar)
        try:
            bars, chord_events = chord_detection_btc.detect_chords_btc(
                audio_path, bars_raw,
                bass_chroma=bass_chroma,
                bass_chroma_times=bass_chroma_times,
                guitar_chroma=guitar_chroma,
                guitar_chroma_times=guitar_chroma_times,
            )
        except Exception as exc:
            job.step_label += f" [fallback legacy chords: {type(exc).__name__}]"
            bars = bars_raw
            chord_events = bars_raw
```

- [ ] **Step 4: Run both fallback tests**

```bash
.venv/bin/python3 -m pytest tests/test_worker_fallback.py -v
```
Expected: both PASS.

- [ ] **Step 5: Commit**

```bash
git add api/worker.py tests/test_worker_fallback.py
git commit -m "feat: BTC fallback to legacy chord detection on exception in worker"
```

---

### Task 3: Tests for BTC wrapper (`chord_detection_btc.py`)

**Files:**
- Create: `tests/test_chord_detection_btc.py`

- [ ] **Step 1: Write tests**

Create `tests/test_chord_detection_btc.py`:

```python
"""Unit tests for pipeline/chord_detection_btc.py.

All tests mock the BTC model — no model weights are loaded.
"""
from unittest.mock import MagicMock, patch
import numpy as np
import pytest
from pipeline.chord_detection import ChordSegment
from pipeline import chord_detection_btc


@pytest.fixture(autouse=True)
def _mock_btc(monkeypatch):
    """Inject a pre-loaded model so _load_model() is a no-op."""
    mock_model = MagicMock()
    mock_model.parameters.return_value = iter([MagicMock(device="cpu")])

    import torch
    # self_attn_layers returns (attn_out, _); output_layer.output_projection returns logits
    fake_logits = torch.zeros(1, 4, 170)
    mock_model.self_attn_layers.return_value = (fake_logits, None)
    mock_model.output_layer.output_projection.return_value = fake_logits

    monkeypatch.setattr(chord_detection_btc, "_model", mock_model)
    monkeypatch.setattr(chord_detection_btc, "_mean", np.float32(0.0))
    monkeypatch.setattr(chord_detection_btc, "_std", np.float32(1.0))
    monkeypatch.setattr(chord_detection_btc, "_idx_to_chord", {
        i: "C:maj" for i in range(170)
    } | {168: "N", 169: "X"})
    monkeypatch.setattr(chord_detection_btc, "_config", MagicMock(
        model={"timestep": 4, "num_chords": 170}
    ))


# ── _btc_to_notara ────────────────────────────────────────────────────────────

def test_btc_to_notara_major():
    assert chord_detection_btc._btc_to_notara("C:maj") == "C"

def test_btc_to_notara_minor():
    assert chord_detection_btc._btc_to_notara("A:min") == "Am"

def test_btc_to_notara_dominant7():
    assert chord_detection_btc._btc_to_notara("G:7") == "G7"

def test_btc_to_notara_sus4():
    assert chord_detection_btc._btc_to_notara("D:sus4") == "Dsus4"

def test_btc_to_notara_nc():
    assert chord_detection_btc._btc_to_notara("N") == "N.C."
    assert chord_detection_btc._btc_to_notara("X") == "N.C."

def test_btc_to_notara_plain_root():
    # No colon — treat as major root
    assert chord_detection_btc._btc_to_notara("Em") == "Em"


# ── _bass_forced_root ─────────────────────────────────────────────────────────

def test_bass_forced_root_strong_signal():
    chroma = np.zeros(12)
    chroma[0] = 1.0  # C dominates clearly
    assert chord_detection_btc._bass_forced_root(chroma) == 0

def test_bass_forced_root_weak_signal():
    # Uniform distribution — no single root dominates above BASS_CLARITY_THRESHOLD
    chroma = np.ones(12) / 12.0
    assert chord_detection_btc._bass_forced_root(chroma) is None

def test_bass_forced_root_zero_total():
    assert chord_detection_btc._bass_forced_root(np.zeros(12)) is None


# ── _apply_bass_crosscheck ────────────────────────────────────────────────────

def test_bass_crosscheck_corrects_root():
    # BTC says "G" but bass strongly says C (index 0)
    chroma = np.zeros(12)
    chroma[0] = 1.0
    result = chord_detection_btc._apply_bass_crosscheck("G", chroma)
    assert result.startswith("C")

def test_bass_crosscheck_agrees_keeps_label():
    # BTC says "C", bass also says C
    chroma = np.zeros(12)
    chroma[0] = 1.0
    assert chord_detection_btc._apply_bass_crosscheck("C", chroma) == "C"

def test_bass_crosscheck_nc_unchanged():
    chroma = np.zeros(12)
    chroma[0] = 1.0
    assert chord_detection_btc._apply_bass_crosscheck("N.C.", chroma) == "N.C."


# ── _group_frame_events ───────────────────────────────────────────────────────

def test_group_frame_events_merges_short_event():
    idx_to_chord = {0: "C:maj", 1: "A:min"}
    # One brief "A:min" frame (0.1 s) surrounded by "C:maj" — below MIN_CHORD_DURATION
    preds = [0, 0, 0, 0, 1, 0, 0, 0]
    events = chord_detection_btc._group_frame_events(preds, 0.1, idx_to_chord, 0.8)
    assert all(e.label != "Am" for e in events)

def test_group_frame_events_keeps_long_event():
    idx_to_chord = {0: "C:maj", 1: "A:min"}
    # 4 frames of "A:min" at 0.1 s/frame = 0.4 s → above MIN_CHORD_DURATION (0.2 s)
    preds = [0, 0, 1, 1, 1, 1, 0, 0]
    events = chord_detection_btc._group_frame_events(preds, 0.1, idx_to_chord, 0.8)
    assert any(e.label == "Am" for e in events)

def test_group_frame_events_empty():
    assert chord_detection_btc._group_frame_events([], 0.1, {}, 1.0) == []


# ── _viterbi_smooth ───────────────────────────────────────────────────────────

def test_viterbi_smooth_returns_same_length():
    log_probs = np.log(np.ones((10, 5)) / 5)
    path = chord_detection_btc._viterbi_smooth(log_probs)
    assert len(path) == 10

def test_viterbi_smooth_strong_signal():
    # Frame 0-4: class 0 dominant; frame 5-9: class 2 dominant
    lp = np.full((10, 5), -10.0)
    lp[:5, 0] = 0.0
    lp[5:, 2] = 0.0
    path = chord_detection_btc._viterbi_smooth(lp, self_loop=0.5)
    assert path[0] == 0
    assert path[9] == 2
```

- [ ] **Step 2: Run tests to verify they pass**

```bash
.venv/bin/python3 -m pytest tests/test_chord_detection_btc.py -v
```
Expected: all PASS (model is mocked, no weights loaded).

- [ ] **Step 3: Commit**

```bash
git add tests/test_chord_detection_btc.py
git commit -m "test: unit tests for chord_detection_btc (mocked BTC model)"
```

---

### Task 4: Tests for SynthTab wrapper (`transcription_synthtab.py`)

**Files:**
- Create: `tests/test_transcription_synthtab.py`

- [ ] **Step 1: Write tests**

Create `tests/test_transcription_synthtab.py`:

```python
"""Unit tests for pipeline/transcription_synthtab.py.

All tests mock the SynthTab model — no model weights are loaded.
"""
import numpy as np
import pytest
from unittest.mock import MagicMock, patch
from pipeline import transcription_synthtab
from pipeline.transcription import Note


@pytest.fixture(autouse=True)
def _mock_synthtab(monkeypatch):
    """Inject a pre-loaded model and CQT so _load() is a no-op."""
    mock_model = MagicMock()
    mock_model.device = "cpu"
    mock_model.parameters.return_value = iter([MagicMock()])
    mock_model.pre_proc.side_effect = lambda b: b
    mock_model.post_proc.side_effect = lambda b: b

    import torch
    # Return (T=10, 6, 1) all-muted tablature
    mock_model.__call__ = MagicMock(return_value=torch.full((1, 10, 6, 1), -1, dtype=torch.int64))

    mock_cqt = MagicMock()
    mock_cqt.process_audio.return_value = np.zeros((1, 192, 10))

    monkeypatch.setattr(transcription_synthtab, "_model", mock_model)
    monkeypatch.setattr(transcription_synthtab, "_cqt", mock_cqt)


# ── _tab_to_notes ─────────────────────────────────────────────────────────────

def test_tab_to_notes_muted_string_no_note():
    tab = np.full((10, 6), -1)
    assert transcription_synthtab._tab_to_notes(tab) == []

def test_tab_to_notes_open_low_e():
    # String 0 (low E) fret 0 for 5 frames → MIDI 40
    tab = np.full((10, 6), -1)
    tab[:5, 0] = 0
    notes = transcription_synthtab._tab_to_notes(tab)
    assert len(notes) == 1
    assert notes[0].pitch == 40  # open low E

def test_tab_to_notes_fret_adds_to_open():
    # String 0 fret 5 for 5 frames → MIDI 40 + 5 = 45 (A)
    tab = np.full((10, 6), -1)
    tab[:5, 0] = 5
    notes = transcription_synthtab._tab_to_notes(tab)
    assert len(notes) == 1
    assert notes[0].pitch == 45

def test_tab_to_notes_short_note_dropped():
    # 1 frame at _HOP_LENGTH/SR ≈ 0.023 s — below _MIN_NOTE_SEC (0.08 s)
    tab = np.full((20, 6), -1)
    tab[0, 0] = 2
    notes = transcription_synthtab._tab_to_notes(tab)
    assert all(n.pitch != 42 for n in notes)

def test_tab_to_notes_multiple_strings():
    tab = np.full((10, 6), -1)
    tab[:5, 0] = 0   # E (MIDI 40)
    tab[:5, 2] = 2   # D string fret 2 = F# (MIDI 52)
    notes = transcription_synthtab._tab_to_notes(tab)
    pitches = {n.pitch for n in notes}
    assert 40 in pitches
    assert 52 in pitches

def test_tab_to_notes_sorted_by_start():
    tab = np.full((20, 6), -1)
    tab[10:15, 0] = 0   # starts at frame 10
    tab[:5, 1] = 0      # starts at frame 0
    notes = transcription_synthtab._tab_to_notes(tab)
    starts = [n.start for n in notes]
    assert starts == sorted(starts)

def test_tab_to_notes_velocity_is_fixed():
    tab = np.full((10, 6), -1)
    tab[:5, 0] = 0
    notes = transcription_synthtab._tab_to_notes(tab)
    assert all(n.velocity == transcription_synthtab._MIN_VELOCITY for n in notes)

def test_open_string_midi_pitches():
    # Verify the open string MIDI mapping matches standard EADGBE
    expected = [40, 45, 50, 55, 59, 64]
    assert transcription_synthtab._OPEN_STRING_MIDI == expected
```

- [ ] **Step 2: Run tests to verify they pass**

```bash
.venv/bin/python3 -m pytest tests/test_transcription_synthtab.py -v
```
Expected: all PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/test_transcription_synthtab.py
git commit -m "test: unit tests for transcription_synthtab (mocked SynthTab model)"
```

---

### Task 5: Benchmark script

**Files:**
- Create: `tests/benchmark.py`

- [ ] **Step 1: Create benchmark script**

Create `tests/benchmark.py`:

```python
#!/usr/bin/env python3
"""Benchmark: compare legacy vs BTC chord detection.

Usage:
    python -m tests.benchmark /path/to/song.wav [/path/to/song2.wav ...]

Each WAV needs a companion `<name>.chords.txt` with one chord label per line
(one per bar, matching the expected bar-aligned output). Lines without a
companion .chords.txt still run — accuracy shows as "N/A".

Output: a table comparing legacy vs BTC chord accuracy per file.
"""
from __future__ import annotations

import math
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import librosa

from pipeline import chord_detection, key_detection, separation, transcription
from pipeline import chord_detection_btc


def _load_expected(wav_path: Path) -> list[str]:
    p = wav_path.with_suffix(".chords.txt")
    if not p.exists():
        return []
    return [l.strip() for l in p.read_text().splitlines() if l.strip()]


def _accuracy(detected: list[str], expected: list[str]) -> float:
    if not expected:
        return float("nan")
    n = min(len(detected), len(expected))
    return sum(d == e for d, e in zip(detected[:n], expected[:n])) / len(expected)


def _fmt(v: float) -> str:
    return f"{v:.1%}" if not math.isnan(v) else "N/A"


def _run_file(wav_path: Path) -> dict:
    print(f"  Processing: {wav_path.name} ...", end=" ", flush=True)
    expected = _load_expected(wav_path)
    work = Path(tempfile.mkdtemp(prefix="notara_bench_"))
    try:
        harmonic, bass_path, guitar_stem = separation.separate(wav_path, work)
        y, sr = librosa.load(str(harmonic), sr=None, mono=True)
        bass_y, bass_sr = librosa.load(str(bass_path), sr=None, mono=True)
        key_est = key_detection.detect_key(y, sr)

        bars_legacy, tempo = chord_detection.detect_chords(y, sr, bass_y, bass_sr, key_est)
        labels_legacy = [b.label for b in bars_legacy]

        try:
            bars_btc, _ = chord_detection_btc.detect_chords_btc(wav_path, bars_legacy)
            labels_btc = [b.label for b in bars_btc]
            btc_ok = True
        except Exception as exc:
            labels_btc = []
            btc_ok = False
            print(f"[BTC failed: {exc}]", end=" ")

        print("done")
        return {
            "file": wav_path.name,
            "tempo": round(tempo, 1),
            "bars": len(bars_legacy),
            "legacy_acc": _accuracy(labels_legacy, expected),
            "btc_acc": _accuracy(labels_btc, expected) if btc_ok else float("nan"),
        }
    finally:
        shutil.rmtree(work, ignore_errors=True)


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    results = [_run_file(Path(p)) for p in sys.argv[1:]]

    print()
    print("=" * 72)
    print(f"{'File':<32} {'Tempo':>6} {'Bars':>5} {'Legacy acc':>12} {'BTC acc':>10}")
    print("-" * 72)
    for r in results:
        print(f"{r['file']:<32} {r['tempo']:>6.1f} {r['bars']:>5} "
              f"{_fmt(r['legacy_acc']):>12} {_fmt(r['btc_acc']):>10}")
    print("=" * 72)

    # Decision helper
    btc_scores = [r["btc_acc"] for r in results if not math.isnan(r["btc_acc"])]
    leg_scores = [r["legacy_acc"] for r in results if not math.isnan(r["legacy_acc"])]
    if btc_scores and leg_scores:
        avg_btc = sum(btc_scores) / len(btc_scores)
        avg_leg = sum(leg_scores) / len(leg_scores)
        diff = avg_btc - avg_leg
        print()
        if diff > 0.05:
            print(f"RECOMMENDATION: BTC is better by {diff:.1%} → keep as default ✓")
        elif diff < -0.05:
            print(f"RECOMMENDATION: Legacy is better by {-diff:.1%} → revert BTC default ✗")
        else:
            print(f"RECOMMENDATION: No significant difference ({diff:+.1%}) → keep BTC (richer vocab)")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Smoke-test the script**

```bash
.venv/bin/python3 -m tests.benchmark --help
```
Expected: prints usage/docstring and exits cleanly.

- [ ] **Step 3: Commit**

```bash
git add tests/benchmark.py
git commit -m "feat: benchmark script — legacy vs BTC chord detection accuracy"
```

---

### Task 6: Verify and commit the frontend lyrics changes

**Files:**
- Modify (verify): `index.html`, `css/main.css`, `js/playback.js`, `js/chords.js`

- [ ] **Step 1: Check what's changed in the frontend**

```bash
cd ~/Library/CloudStorage/GoogleDrive-davisthe8th@gmail.com/My\ Drive/GARAGEBAND/VALLETOFNOONE/guitar_tab_pipeline
git diff index.html css/main.css js/playback.js
git status js/chords.js
```

- [ ] **Step 2: Verify the lyrics UI in index.html**

Confirm `index.html` has:
- A collapsible `<section>` or `<div>` for lyrics input below the drop zone
- A `<textarea>` with id `lyrics-text` for pasted lyrics
- A file input accepting `.txt` and `.docx` for lyrics file upload
- The "Lyrics" tab in the results tab switcher

If any of these are missing, add them following the existing toggle pattern in `index.html`.

- [ ] **Step 3: Verify css/main.css has lyrics styles**

Confirm `css/main.css` has:
- Style for `.lyrics-section` (collapsible container)
- Style for chord lines (red `--red` color, monospace font)
- Style for the `lyrics` tab button in the tab switcher

If missing, add using the existing Warm Ruby palette tokens.

- [ ] **Step 4: Verify js/app.js handles lyrics tab**

Confirm `js/app.js`:
- Reads the lyrics textarea and file input on submit
- Appends `lyrics_text` or `lyrics_file` to the `FormData`
- Renders a "Lyrics" tab button when `data.tabs.lyrics` is present
- `_renderTab("lyrics", ...)` renders the chord chart with red chord lines

- [ ] **Step 5: Verify js/playback.js chord_events support**

Confirm `js/playback.js`:
- Uses `resultsData.bars` (chord events from BTC — frame-level precision, not bar-aligned)
- `_syncTab` correctly handles the now-variable bar durations from BTC

- [ ] **Step 6: Run all tests**

```bash
.venv/bin/python3 -m pytest -q
```
Expected: all tests pass.

- [ ] **Step 7: Commit the full Sprint 1+2 feature set**

```bash
git add index.html css/main.css js/app.js js/playback.js js/chords.js \
    pipeline/chord_detection.py pipeline/separation.py \
    .gitignore install.bat install.sh
git commit -m "feat: lyrics chord chart, BTC chord detection, SynthTab transcription — Sprint 1+2"
```

---

### Task 7: Full test suite green check

**Files:** None

- [ ] **Step 1: Run full pytest**

```bash
.venv/bin/python3 -m pytest -v
```
Expected: all 57+ tests pass (including new test_chord_detection_btc, test_transcription_synthtab, test_worker_fallback).

- [ ] **Step 2: Confirm git log looks clean**

```bash
git log --oneline -8
```
Expected: 5 commits from this sprint visible on top.
