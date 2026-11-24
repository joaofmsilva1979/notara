# Multi-Guitar + Bass Recognition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add multi-guitar separation (stereo L/R channel split of the Demucs guitar stem as guitar 1 / guitar 2), dedicated bass tab output (4-string fretboard), extended chord vocabulary (sus2/sus4/dim/aug/dim7/m7b5), and a position-window fretboard heuristic that produces more playable tab.

**Architecture:** Six isolated changes, each independently testable. (1) `tuning.py` gains a separate `BASS_TUNINGS` list so the existing 7-entry `TUNINGS` guard stays green and `suggest_alternate_tuning` never proposes bass tunings for a guitar track. (2) `chord_detection.py` gets six new chord quality templates — pure data addition, no logic change. (3) `fretboard.py` tracks a sliding 4-fret position window so consecutive notes stay in the same neck region instead of always jumping to the lowest possible fret. (4) `tab_render.py` replaces every hardcoded `6` / `5` string-count with `len(tuning.string_names)`, allowing 4-string bass tabs to render correctly. (5) `separation.py` adds `separate_guitars()` which reuses the existing Demucs run but additionally splits the stereo guitar stem into L/R mono files. (6) `main.py` adds `--multi-guitar` / `--bass-tuning` flags that wire all of the above into a three-track output pipeline (guitar 1, guitar 2, bass).

**Tech Stack:** Python 3.9, pytest, numpy, librosa, soundfile, basic-pitch, demucs (existing stack — no new dependencies).

---

## Environment note (same as all prior plans)

All commands assume the working directory is the `guitar_tab_pipeline/` project root. Always invoke tools as `./.venv/bin/python3 -m <tool>` (e.g. `-m pytest`), never the bare script wrappers — their shebangs are broken from an earlier Google Drive folder rename.

---

## Files

| File | Action | What changes |
|---|---|---|
| `pipeline/tuning.py` | Modify | Add `BASS_STANDARD_EADG`, `BASS_DROP_D`, `BASS_5_STRING_BEADG` constants + `BASS_TUNINGS` list; update `find_tuning` to search both lists |
| `pipeline/chord_detection.py` | Modify | Append sus2, sus4, dim, aug, dim7, m7b5 to `CHORD_TYPES` |
| `pipeline/fretboard.py` | Modify | Add `POSITION_SPAN = 4`; rewrite `map_notes_to_fretboard` with sliding window |
| `pipeline/tab_render.py` | Modify | Replace hardcoded `6` / `5` with `n_strings = len(tuning.string_names)` in `_new_bar_grid`, `_place_note`, `render_tab` |
| `pipeline/separation.py` | Modify | Extract `_run_demucs` helper; add `separate_guitars()` returning `(guitar1, guitar2_or_None, bass_stem, harmonic_mix)` |
| `main.py` | Modify | Add `--multi-guitar` / `--bass-tuning` flags; add multi-guitar pipeline branch in `main()` |
| `tests/test_tuning.py` | Modify | Update `test_tunings_catalog_has_seven_entries` → check guitar list stays at 7; add bass tuning tests |
| `tests/test_chord_detection.py` | Modify | Add tests for two new chord qualities |
| `tests/test_fretboard.py` | Modify | Add position-window tests |
| `tests/test_tab_render.py` | Modify | Add 4-string bass tab render test |
| `tests/test_main_args.py` | Modify | Add `--multi-guitar` / `--bass-tuning` argparse tests |

---

## Task 1 — Bass tunings

**Files:**
- Modify: `pipeline/tuning.py`
- Modify: `tests/test_tuning.py`

- [ ] **Step 1: Write the failing tests**

Add to the end of `tests/test_tuning.py`:

```python
from pipeline.tuning import (
    BASS_TUNINGS,
    BASS_STANDARD_EADG,
    BASS_DROP_D,
    BASS_5_STRING_BEADG,
)


def test_guitar_tunings_catalog_still_has_seven_entries():
    assert len(TUNINGS) == 7


def test_bass_tunings_catalog_has_three_entries():
    assert len(BASS_TUNINGS) == 3


def test_find_tuning_returns_bass_standard():
    t = find_tuning(BASS_STANDARD_EADG)
    assert t.open_string_midi == [28, 33, 38, 43]
    assert t.string_names == ["E", "A", "D", "G"]


def test_find_tuning_returns_bass_drop_d():
    t = find_tuning(BASS_DROP_D)
    assert t.open_string_midi == [26, 33, 38, 43]
    assert t.string_names == ["D", "A", "D", "G"]


def test_find_tuning_returns_bass_5_string():
    t = find_tuning(BASS_5_STRING_BEADG)
    assert t.open_string_midi == [23, 28, 33, 38, 43]
    assert t.string_names == ["B", "E", "A", "D", "G"]


def test_suggest_alternate_tuning_never_suggests_bass_for_guitar_notes():
    standard = find_tuning(STANDARD_E_A_D_G_B_E)
    # notes all within normal guitar range — no bass tuning should be suggested
    notes = [_note(40), _note(45), _note(50), _note(55), _note(59), _note(64),
             _note(40), _note(45), _note(50)]
    suggestion = suggest_alternate_tuning(notes, standard)
    if suggestion is not None:
        assert suggestion.suggested.name not in (BASS_STANDARD_EADG, BASS_DROP_D, BASS_5_STRING_BEADG)
```

- [ ] **Step 2: Run to verify failure**

```bash
./.venv/bin/python3 -m pytest tests/test_tuning.py -v 2>&1 | tail -20
```
Expected: `ImportError` on `BASS_TUNINGS`, `BASS_STANDARD_EADG`, etc.

- [ ] **Step 3: Implement**

In `pipeline/tuning.py`, directly after the existing tuning name constants (`OPEN_D = ...`) add:

```python
BASS_STANDARD_EADG = "Bass Standard EADG"
BASS_DROP_D = "Bass Drop D"
BASS_5_STRING_BEADG = "Bass 5-String BEADG"
```

Then replace the existing `TUNINGS: List[Tuning] = [...]` block with:

```python
TUNINGS: List[Tuning] = [
    Tuning(STANDARD_E_A_D_G_B_E, [40, 45, 50, 55, 59, 64], ["E", "A", "D", "G", "B", "e"]),
    Tuning(DROP_D, [38, 45, 50, 55, 59, 64], ["D", "A", "D", "G", "B", "e"]),
    Tuning(EB_STANDARD, [39, 44, 49, 54, 58, 63], ["Eb", "Ab", "Db", "Gb", "Bb", "eb"]),
    Tuning(D_STANDARD, [38, 43, 48, 53, 57, 62], ["D", "G", "C", "F", "A", "d"]),
    Tuning(DROP_C_SHARP, [37, 44, 49, 54, 58, 63], ["C#", "Ab", "Db", "Gb", "Bb", "eb"]),
    Tuning(OPEN_G, [38, 43, 50, 55, 59, 62], ["D", "G", "D", "G", "B", "d"]),
    Tuning(OPEN_D, [38, 45, 50, 54, 57, 62], ["D", "A", "D", "F#", "A", "d"]),
]

# Bass tunings kept separate so suggest_alternate_tuning never proposes a
# bass tuning as an alternative for a guitar track.
BASS_TUNINGS: List[Tuning] = [
    Tuning(BASS_STANDARD_EADG, [28, 33, 38, 43], ["E", "A", "D", "G"]),
    Tuning(BASS_DROP_D, [26, 33, 38, 43], ["D", "A", "D", "G"]),
    Tuning(BASS_5_STRING_BEADG, [23, 28, 33, 38, 43], ["B", "E", "A", "D", "G"]),
]
```

Then replace `find_tuning`:

```python
def find_tuning(name: str) -> Tuning:
    for tuning in TUNINGS + BASS_TUNINGS:
        if tuning.name == name:
            return tuning
    raise ValueError(f"Unknown tuning: {name!r}")
```

- [ ] **Step 4: Run tests**

```bash
./.venv/bin/python3 -m pytest tests/test_tuning.py -v 2>&1 | tail -20
```
Expected: all tuning tests pass (the old `test_tunings_catalog_has_seven_entries` is replaced by `test_guitar_tunings_catalog_still_has_seven_entries` which checks the same thing).

- [ ] **Step 5: Commit**

```bash
git add pipeline/tuning.py tests/test_tuning.py
git commit -m "feat: add bass tunings (EADG, Drop D, 5-string BEADG) as separate BASS_TUNINGS list"
```

---

## Task 2 — Extended chord templates

**Files:**
- Modify: `pipeline/chord_detection.py`
- Modify: `tests/test_chord_detection.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_chord_detection.py`:

```python
import numpy as np
from pipeline.chord_detection import _best_chord
from pipeline.key_detection import KeyEstimate


def _chroma_for_intervals(root: int, intervals: list) -> np.ndarray:
    """Synthetic chroma vector with energy only on the given intervals from root."""
    vec = np.zeros(12)
    for i in intervals:
        vec[(root + i) % 12] = 1.0
    return vec


def test_best_chord_detects_sus4():
    # E sus4 = E (0), A (5), B (7) from root E=4
    chroma = _chroma_for_intervals(4, [0, 5, 7])
    label, score = _best_chord(chroma)
    assert label == "Esus4"
    assert score > 0.8


def test_best_chord_detects_dim():
    # A dim = A (0), C (3), Eb (6) from root A=9
    chroma = _chroma_for_intervals(9, [0, 3, 6])
    label, score = _best_chord(chroma)
    assert label == "Adim"
    assert score > 0.8


def test_best_chord_detects_sus2():
    # D sus2 = D (0), E (2), A (7) from root D=2
    chroma = _chroma_for_intervals(2, [0, 2, 7])
    label, score = _best_chord(chroma)
    assert label == "Dsus2"
    assert score > 0.8
```

- [ ] **Step 2: Run to verify failure**

```bash
./.venv/bin/python3 -m pytest tests/test_chord_detection.py::test_best_chord_detects_sus4 tests/test_chord_detection.py::test_best_chord_detects_dim tests/test_chord_detection.py::test_best_chord_detects_sus2 -v 2>&1 | tail -20
```
Expected: FAIL — labels like `Esus4` don't exist in templates yet.

- [ ] **Step 3: Implement**

In `pipeline/chord_detection.py`, replace the `CHORD_TYPES` constant:

```python
CHORD_TYPES = [
    ("", [0, 4, 7]),          # major
    ("m", [0, 3, 7]),         # minor
    ("7", [0, 4, 7, 10]),     # dominant 7th
    ("maj7", [0, 4, 7, 11]),  # major 7th
    ("m7", [0, 3, 7, 10]),    # minor 7th
    ("sus2", [0, 2, 7]),      # suspended 2nd
    ("sus4", [0, 5, 7]),      # suspended 4th
    ("dim", [0, 3, 6]),       # diminished
    ("aug", [0, 4, 8]),       # augmented
    ("dim7", [0, 3, 6, 9]),   # diminished 7th
    ("m7b5", [0, 3, 6, 10]),  # half-diminished (minor 7 flat 5)
]
```

- [ ] **Step 4: Run tests**

```bash
./.venv/bin/python3 -m pytest tests/test_chord_detection.py -v 2>&1 | tail -20
```
Expected: all chord detection tests pass.

- [ ] **Step 5: Commit**

```bash
git add pipeline/chord_detection.py tests/test_chord_detection.py
git commit -m "feat: extend chord vocabulary with sus2, sus4, dim, aug, dim7, m7b5 (132 templates total)"
```

---

## Task 3 — Position-window fretboard mapping

**Files:**
- Modify: `pipeline/fretboard.py`
- Modify: `tests/test_fretboard.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_fretboard.py`:

```python
def test_position_window_keeps_sequential_notes_in_same_region():
    """Notes that can be played in frets 5-9 should not jump down to fret 0
    once the window has shifted up, unless the note can only be played there."""
    tuning = find_tuning(STANDARD_E_A_D_G_B_E)
    # MIDI 65 = F4, fret 1 on e string OR fret 6 on B string
    # MIDI 67 = G4, fret 3 on e string OR fret 8 on B string
    # MIDI 69 = A4, fret 5 on e string OR fret 10 on B string
    # Play three notes: start with the high-fret option to shift the window up,
    # then subsequent notes should stay in that region.
    notes = [
        _note(69, start=0.0),   # A4 — forces window to fret 5-9
        _note(67, start=0.1),   # G4 — fret 8 on B is in window; fret 3 on e is not
        _note(65, start=0.2),   # F4 — fret 6 on B is in window; fret 1 on e is not
    ]
    fretted = map_notes_to_fretboard(notes, tuning)
    assert len(fretted) == 3
    # All three notes should land on frets >= 5 (staying in the shifted window)
    assert all(fn.fret >= 5 for fn in fretted), (
        f"Expected all frets >= 5, got {[fn.fret for fn in fretted]}"
    )


def test_open_strings_always_allowed_regardless_of_window():
    """Open strings (fret 0) are always valid even after window has shifted up."""
    tuning = find_tuning(STANDARD_E_A_D_G_B_E)
    # MIDI 40 = E2 = open low E string (fret 0, string 0) — only option
    # After any window shift, open string must still be used
    notes = [
        _note(69, start=0.0),  # shifts window up
        _note(40, start=0.1),  # only playable at fret 0, string 0
    ]
    fretted = map_notes_to_fretboard(notes, tuning)
    open_e = [fn for fn in fretted if fn.pitch == 40]
    assert len(open_e) == 1
    assert open_e[0].fret == 0
```

- [ ] **Step 2: Run to verify failure**

```bash
./.venv/bin/python3 -m pytest tests/test_fretboard.py::test_position_window_keeps_sequential_notes_in_same_region tests/test_fretboard.py::test_open_strings_always_allowed_regardless_of_window -v 2>&1 | tail -20
```
Expected: `test_position_window_keeps_sequential_notes_in_same_region` FAIL (current code picks lowest fret, jumping to fret 3 for G4 and fret 1 for F4).

- [ ] **Step 3: Implement**

In `pipeline/fretboard.py`, add the constant after the existing `CHORD_TOLERANCE` line:

```python
POSITION_SPAN = 4  # fret span of one neck position (e.g. frets 5–9)
```

Then replace `map_notes_to_fretboard`:

```python
def map_notes_to_fretboard(notes: List[Note], tuning: Optional[Tuning] = None) -> List[FrettedNote]:
    if tuning is None:
        tuning = find_tuning(STANDARD_E_A_D_G_B_E)
    fretted: List[FrettedNote] = []
    position_start = 0  # left edge of the current 4-fret position window

    for group in _group_by_onset(notes):
        used_strings: set = set()
        for note in sorted(group, key=lambda n: -n.pitch):
            chosen: Optional[tuple] = None

            # First pass: prefer frets within the current window, or open strings
            for string_idx, fret in _fret_options(note.pitch, tuning):
                if string_idx not in used_strings:
                    if fret == 0 or position_start <= fret <= position_start + POSITION_SPAN:
                        chosen = (string_idx, fret)
                        break

            # Second pass: fall back to lowest available fret on any free string
            if chosen is None:
                for string_idx, fret in _fret_options(note.pitch, tuning):
                    if string_idx not in used_strings:
                        chosen = (string_idx, fret)
                        break

            if chosen is None:
                continue  # out of range or no free string left; note dropped

            string_idx, fret = chosen
            used_strings.add(string_idx)

            # Shift window when a non-open fret lands outside it
            if fret > 0 and not (position_start <= fret <= position_start + POSITION_SPAN):
                position_start = max(0, fret - 2)

            fretted.append(FrettedNote(
                string=string_idx, fret=fret,
                start=note.start, end=note.end, pitch=note.pitch,
            ))

    fretted.sort(key=lambda fn: fn.start)
    return fretted
```

- [ ] **Step 4: Run full test suite**

```bash
./.venv/bin/python3 -m pytest tests/test_fretboard.py -v 2>&1 | tail -20
```
Expected: all fretboard tests pass (the three original tests still pass because fret=0 open strings are always allowed by the window logic).

- [ ] **Step 5: Commit**

```bash
git add pipeline/fretboard.py tests/test_fretboard.py
git commit -m "feat: position-window fretboard mapping — stay in a 4-fret region instead of always jumping to lowest fret"
```

---

## Task 4 — Dynamic string count in tab_render (bass tab support)

**Files:**
- Modify: `pipeline/tab_render.py`
- Modify: `tests/test_tab_render.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_tab_render.py`:

```python
from pipeline.tuning import BASS_STANDARD_EADG


def test_bass_tab_renders_four_string_rows():
    bars = [_bar(0, 0.0, 2.0, "Em")]
    key = KeyEstimate(tonic="E", mode="minor", correlation=0.9)
    bass_tuning = find_tuning(BASS_STANDARD_EADG)
    text = render_tab(bars, [], key, 120.0, "song.wav", bass_tuning)
    lines = text.splitlines()
    string_rows = [l for l in lines if "|" in l and not l.startswith("#")]
    # Should have exactly 4 string rows per line group (not 6)
    assert len(string_rows) == 4
    # Lowest string label should be E (not a sixth string)
    assert any(l.startswith("E|") for l in string_rows)
    # Should NOT have guitar-only strings B or high-e
    assert not any(l.startswith("B|") for l in string_rows)
    assert not any(l.startswith("e|") for l in string_rows)
```

- [ ] **Step 2: Run to verify failure**

```bash
./.venv/bin/python3 -m pytest tests/test_tab_render.py::test_bass_tab_renders_four_string_rows -v 2>&1 | tail -15
```
Expected: FAIL — 6 string rows render instead of 4.

- [ ] **Step 3: Implement**

In `pipeline/tab_render.py`, replace these three functions:

```python
def _new_bar_grid(n_strings: int) -> List[List[str]]:
    return [["-"] * COLUMNS_PER_BAR for _ in range(n_strings)]


def _place_note(grid: List[List[str]], note: FrettedNote, bar: ChordSegment,
                n_strings: int) -> None:
    bar_len = bar.end - bar.start
    if bar_len <= 0:
        col = 0
    else:
        col = int(round((note.start - bar.start) / bar_len * COLUMNS_PER_BAR))
        col = max(0, min(COLUMNS_PER_BAR - 1, col))
    # display rows: row 0 = highest string ... row (n_strings-1) = lowest string
    row = (n_strings - 1) - note.string
    grid[row][col] = str(note.fret)


def render_tab(bars: List[ChordSegment], notes: List[FrettedNote],
               key_estimate: KeyEstimate, tempo: float,
               source_name: str, tuning: Tuning = None, bars_per_line: int = 4) -> str:
    if tuning is None:
        tuning = find_tuning(STANDARD_E_A_D_G_B_E)
    n_strings = len(tuning.string_names)
    out = []
    out.append(f"# Tab generated from: {source_name}")
    out.append(f"# Estimated key: {key_estimate}  (correlation={key_estimate.correlation:.2f})")
    out.append(f"# Estimated tempo: {tempo:.1f} BPM (assumed 4/4)")
    out.append(f"# Tuning: {tuning.name}")
    out.append("#")
    out.append("# LIMITS: chords/positions/rhythm below are approximate -- see")
    out.append("# pipeline/*.py module docstrings for known limitations of each stage.")
    out.append("")

    notes_by_bar: List[List[FrettedNote]] = [[] for _ in bars]
    bar_starts = [b.start for b in bars]
    for note in notes:
        idx = None
        for i, b in enumerate(bars):
            if b.start <= note.start < b.end:
                idx = i
                break
        if idx is None and bar_starts:
            if note.start >= bar_starts[-1]:
                idx = len(bars) - 1
        if idx is not None:
            notes_by_bar[idx].append(note)

    for line_start in range(0, len(bars), bars_per_line):
        chunk = bars[line_start:line_start + bars_per_line]

        chord_row = "  ".join(
            f"{b.label:<{COLUMNS_PER_BAR}}" for b in chunk
        )
        out.append(chord_row.rstrip())

        grids = []
        for i, bar in enumerate(chunk):
            grid = _new_bar_grid(n_strings)
            for note in notes_by_bar[line_start + i]:
                _place_note(grid, note, bar, n_strings)
            grids.append(grid)

        for row_idx in range(n_strings):
            row_str = tuning.string_names[(n_strings - 1) - row_idx] + "|"
            for grid in grids:
                cells = [cell.ljust(CELL_WIDTH, "-") for cell in grid[row_idx]]
                row_str += "".join(cells) + "|"
            out.append(row_str)

        out.append("")

    return "\n".join(out)
```

- [ ] **Step 4: Run full test suite**

```bash
./.venv/bin/python3 -m pytest tests/test_tab_render.py tests/test_pdf_export.py -v 2>&1 | tail -20
```
Expected: all tests pass. (PDF export calls `render_tab` internally; the pagination logic is unchanged since it only counts lines.)

- [ ] **Step 5: Commit**

```bash
git add pipeline/tab_render.py tests/test_tab_render.py
git commit -m "feat: dynamic string count in tab_render — enables 4-string bass tab"
```

---

## Task 5 — Multi-guitar stereo separation

**Files:**
- Modify: `pipeline/separation.py`

No new unit tests — `separate_guitars` shells out to Demucs (same situation as `separate`). Manual smoke test in Task 6 covers end-to-end.

- [ ] **Step 1: Verify the existing function still works (regression guard)**

```bash
./.venv/bin/python3 -c "import ast; ast.parse(open('pipeline/separation.py').read()); print('syntax ok')"
```
Expected: `syntax ok`

- [ ] **Step 2: Implement**

Replace the entire content of `pipeline/separation.py` with:

```python
"""Step 1: source separation with Demucs.

Uses the 6-stem model (htdemucs_6s), which has a dedicated "guitar" stem
in addition to drums/bass/vocals/piano/other. We combine guitar + other
into a single "harmonic" mix (for transcription and key detection) and
also return the separated bass stem on its own (used by chord_detection.py
to constrain the chord root). Drums/vocals/piano are still discarded.

Known limitation: everything downstream depends on how well Demucs isolates
guitar content. Bleed from drums/vocals into the guitar stem (or guitar
content leaking into "other"/"piano") will directly corrupt note detection.
Distorted/heavily effected electric guitar separates worse than clean
acoustic or electric guitar.

Multi-guitar note: separate_guitars() splits the guitar stem's stereo
channels into left (guitar 1) and right (guitar 2) mono files. This works
well for recordings where two guitars are panned to opposite sides (common
in rock/pop). For mono recordings or songs where guitars share the same
pan position, guitar2_path will be None (mono source) or effectively
identical to guitar1_path (same-pan stereo). In those cases the output
is the same as single-guitar mode.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Optional, Tuple

import numpy as np
import soundfile as sf

DEMUCS_MODEL = "htdemucs_6s"
HARMONIC_STEMS = ("guitar", "other")


def _run_demucs(audio_path: Path, out_dir: Path, device: str) -> Path:
    """Run Demucs and return the stem directory for the track."""
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable, "-m", "demucs",
        "-n", DEMUCS_MODEL,
        "-d", device,
        "-o", str(out_dir),
        str(audio_path),
    ]
    subprocess.run(cmd, check=True)
    stem_dir = out_dir / DEMUCS_MODEL / audio_path.stem
    if not stem_dir.exists():
        raise FileNotFoundError(f"Demucs did not produce expected output at {stem_dir}")
    return stem_dir


def _combine_stems(stem_dir: Path, work_dir: Path) -> Path:
    signals = []
    sr = None
    for stem_name in HARMONIC_STEMS:
        stem_path = stem_dir / f"{stem_name}.wav"
        if not stem_path.exists():
            continue
        y, file_sr = sf.read(stem_path, always_2d=False)
        if sr is None:
            sr = file_sr
        elif file_sr != sr:
            raise ValueError(f"Sample rate mismatch between stems: {file_sr} vs {sr}")
        # collapse to mono for harmonic mix
        signals.append(y if y.ndim == 1 else y.mean(axis=1))

    if not signals:
        raise FileNotFoundError(f"No harmonic stems found in {stem_dir}")

    max_len = max(len(s) for s in signals)
    mix = np.zeros(max_len, dtype=np.float64)
    for s in signals:
        mix[: len(s)] += s

    peak = np.max(np.abs(mix))
    if peak > 1.0:
        mix = mix / peak * 0.98

    harmonic_path = work_dir / "harmonic_mix.wav"
    sf.write(harmonic_path, mix, sr)
    return harmonic_path


def separate(audio_path: Path, work_dir: Path, device: str = "cpu") -> tuple[Path, Path]:
    """Run Demucs and return (harmonic_mix_path, bass_stem_path)."""
    out_dir = work_dir / "stems"
    stem_dir = _run_demucs(audio_path, out_dir, device)

    bass_stem_path = stem_dir / "bass.wav"
    if not bass_stem_path.exists():
        raise FileNotFoundError(f"Demucs did not produce a bass stem at {bass_stem_path}")

    harmonic_path = _combine_stems(stem_dir, work_dir)
    return harmonic_path, bass_stem_path


def separate_guitars(
    audio_path: Path, work_dir: Path, device: str = "cpu"
) -> Tuple[Path, Optional[Path], Path, Path]:
    """Run Demucs and return (guitar1_path, guitar2_path_or_None, bass_path, harmonic_mix_path).

    guitar1 = left channel of the Demucs guitar stem (mono WAV).
    guitar2 = right channel of the Demucs guitar stem (mono WAV), or None if
              the guitar stem is mono (single-channel source).
    bass_path = raw Demucs bass stem (stereo, used as-is for bass transcription).
    harmonic_mix = guitar + other combined mono mix (for key/chord detection,
                   same as what separate() returns).
    """
    out_dir = work_dir / "stems"
    stem_dir = _run_demucs(audio_path, out_dir, device)

    bass_stem_path = stem_dir / "bass.wav"
    if not bass_stem_path.exists():
        raise FileNotFoundError(f"Demucs did not produce a bass stem at {bass_stem_path}")

    guitar_stem_path = stem_dir / "guitar.wav"
    if not guitar_stem_path.exists():
        raise FileNotFoundError(f"Demucs did not produce a guitar stem at {guitar_stem_path}")

    harmonic_path = _combine_stems(stem_dir, work_dir)

    # Split guitar stem into L/R channels
    guitar_data, guitar_sr = sf.read(str(guitar_stem_path))
    if guitar_data.ndim == 1 or guitar_data.shape[1] < 2:
        # Mono source — single guitar track only
        guitar1_path = work_dir / "guitar1.wav"
        mono = guitar_data if guitar_data.ndim == 1 else guitar_data[:, 0]
        sf.write(str(guitar1_path), mono, guitar_sr)
        return guitar1_path, None, bass_stem_path, harmonic_path

    left = guitar_data[:, 0]
    right = guitar_data[:, 1]
    guitar1_path = work_dir / "guitar1.wav"
    guitar2_path = work_dir / "guitar2.wav"
    sf.write(str(guitar1_path), left, guitar_sr)
    sf.write(str(guitar2_path), right, guitar_sr)
    return guitar1_path, guitar2_path, bass_stem_path, harmonic_path
```

- [ ] **Step 3: Verify syntax**

```bash
./.venv/bin/python3 -c "import ast; ast.parse(open('pipeline/separation.py').read()); print('syntax ok')"
```
Expected: `syntax ok`

- [ ] **Step 4: Verify existing imports still work**

```bash
./.venv/bin/python3 -c "from pipeline import separation; print('import ok')"
```
Expected: `import ok`

- [ ] **Step 5: Commit**

```bash
git add pipeline/separation.py
git commit -m "feat: add separate_guitars() — stereo L/R split of Demucs guitar stem for two-guitar output"
```

---

## Task 6 — Wire --multi-guitar into main.py

**Files:**
- Modify: `main.py`
- Modify: `tests/test_main_args.py`

- [ ] **Step 1: Read the existing test_main_args.py to understand current argparse tests**

```bash
./.venv/bin/python3 -m pytest tests/test_main_args.py -v 2>&1 | tail -20
```
Expected: all existing argparse tests pass.

- [ ] **Step 2: Write the failing tests**

Add to `tests/test_main_args.py`:

```python
from pipeline.tuning import BASS_STANDARD_EADG


def test_multi_guitar_flag_defaults_to_false(tmp_path):
    wav = tmp_path / "s.wav"
    wav.touch()
    args = parse_args_for_test([str(wav)])
    assert args.multi_guitar is False


def test_multi_guitar_flag_can_be_set(tmp_path):
    wav = tmp_path / "s.wav"
    wav.touch()
    args = parse_args_for_test([str(wav), "--multi-guitar"])
    assert args.multi_guitar is True


def test_bass_tuning_defaults_to_standard(tmp_path):
    wav = tmp_path / "s.wav"
    wav.touch()
    args = parse_args_for_test([str(wav)])
    assert args.bass_tuning == BASS_STANDARD_EADG


def test_bass_tuning_can_be_set(tmp_path):
    wav = tmp_path / "s.wav"
    wav.touch()
    from pipeline.tuning import BASS_DROP_D
    args = parse_args_for_test([str(wav), "--bass-tuning", BASS_DROP_D])
    assert args.bass_tuning == BASS_DROP_D
```

Note: `parse_args_for_test` must be the helper already in `tests/test_main_args.py` that calls `parse_args([...])` from `main`. If it does not exist yet, add this helper at the top of the test file:

```python
import sys
sys.path.insert(0, ".")
from main import parse_args as _parse_args


def parse_args_for_test(argv):
    return _parse_args(argv)
```

- [ ] **Step 3: Run to verify failure**

```bash
./.venv/bin/python3 -m pytest tests/test_main_args.py::test_multi_guitar_flag_defaults_to_false tests/test_main_args.py::test_bass_tuning_defaults_to_standard -v 2>&1 | tail -15
```
Expected: FAIL — `--multi-guitar` and `--bass-tuning` not recognized.

- [ ] **Step 4: Add new imports and flags to main.py**

At the top of `main.py`, `parse_args` currently imports from `pipeline`. Verify the pipeline import line includes `separation` and add `BASS_STANDARD_EADG` to the tuning import:

Change:
```python
from pipeline import chord_detection, fretboard, key_detection, midi_export, pdf_export, separation, tab_render, transcription, tuning, voice_split
```
to (no change needed — all modules already imported).

In `parse_args()`, add after the existing `--tuning` argument:

```python
    parser.add_argument("--multi-guitar", action="store_true", default=False,
                         help="Separate into guitar 1 (left), guitar 2 (right), and bass — "
                              "produces three tab files instead of one. Works best for "
                              "stereo recordings with guitars panned left/right.")
    parser.add_argument("--bass-tuning", default=tuning.BASS_STANDARD_EADG,
                         choices=[t.name for t in tuning.BASS_TUNINGS],
                         help="Bass guitar tuning for --multi-guitar output "
                              f"(default: {tuning.BASS_STANDARD_EADG})")
```

- [ ] **Step 5: Add the multi-guitar pipeline branch in main()**

In `main()`, locate the `try:` block. Currently it starts with `[1/7] Separating sources...`. Wrap the existing block with an `if not args.multi_guitar:` check and add the new branch. Replace the entire `try:` block with:

```python
    try:
        if args.multi_guitar:
            print("[1/8] Separating sources with Demucs (htdemucs_6s, multi-guitar mode)...")
            guitar1_path, guitar2_path, bass_stem_path, harmonic_path = separation.separate_guitars(
                audio_path, work_dir, device=args.device
            )

            print("[2/8] Transcribing Guitar 1 (left channel)...")
            notes_g1 = transcription.transcribe(guitar1_path)
            print(f"       -> {len(notes_g1)} notes detected")

            if guitar2_path is not None:
                print("[3/8] Transcribing Guitar 2 (right channel)...")
                notes_g2 = transcription.transcribe(guitar2_path)
                print(f"       -> {len(notes_g2)} notes detected")
            else:
                print("[3/8] Mono source — single guitar track only (no Guitar 2)")
                notes_g2 = None

            print("[4/8] Transcribing bass...")
            notes_bass = transcription.transcribe(bass_stem_path)
            print(f"       -> {len(notes_bass)} notes detected")

            print("[5/8] Confirming tuning...")
            selected_tuning = tuning.find_tuning(args.tuning)
            suggestion = tuning.suggest_alternate_tuning(notes_g1, selected_tuning)
            if suggestion is not None:
                print(f"       NOTE: {selected_tuning.name} doesn't fully match Guitar 1.")
                print(f"       Suggestion: {suggestion.suggested.name} "
                      f"(confidence={suggestion.confidence:.2f}). Re-run with "
                      f"--tuning \"{suggestion.suggested.name}\" if that's correct.")
            else:
                print(f"       -> {selected_tuning.name} confirmed")

            print("[6/8] Detecting key and chords...")
            y, sr = librosa.load(harmonic_path, sr=None, mono=True)
            bass_y, bass_sr = librosa.load(bass_stem_path, sr=None, mono=True)
            key_estimate = key_detection.detect_key(y, sr)
            print(f"       -> Key: {key_estimate} (correlation={key_estimate.correlation:.2f})")
            chords, tempo = chord_detection.detect_chords(y, sr, bass_y, bass_sr, key_estimate)
            print(f"       -> {len(chords)} bars, tempo ~{tempo:.1f} BPM")

            print("[7/8] Mapping notes to fretboard...")
            fretted_g1 = fretboard.map_notes_to_fretboard(notes_g1, selected_tuning)
            fretted_g2 = fretboard.map_notes_to_fretboard(notes_g2, selected_tuning) if notes_g2 else []
            bass_tuning_obj = tuning.find_tuning(args.bass_tuning)
            fretted_bass = fretboard.map_notes_to_fretboard(notes_bass, bass_tuning_obj)

            print("[8/8] Rendering tabs...")
            g1_label = f"{audio_path.name} (guitare 1 — canal gauche)"
            g1_path = output_path.with_name(f"{output_path.stem}_guitare1.txt")
            tab_render.write_tab(g1_path, chords, fretted_g1, key_estimate, tempo,
                                  g1_label, tuning=selected_tuning)

            if notes_g2 is not None:
                g2_label = f"{audio_path.name} (guitare 2 — canal droit)"
                g2_path = output_path.with_name(f"{output_path.stem}_guitare2.txt")
                tab_render.write_tab(g2_path, chords, fretted_g2, key_estimate, tempo,
                                      g2_label, tuning=selected_tuning)

            bass_label = f"{audio_path.name} (basse — {bass_tuning_obj.name})"
            bass_tab_path = output_path.with_name(f"{output_path.stem}_basse.txt")
            tab_render.write_tab(bass_tab_path, chords, fretted_bass, key_estimate, tempo,
                                  bass_label, tuning=bass_tuning_obj)

            if args.export_pdf:
                pdf_export.export_pdf(
                    g1_path.with_suffix(".pdf"), chords, fretted_g1, key_estimate, tempo,
                    g1_label, selected_tuning, font_size=args.pdf_font_size
                )
                if notes_g2 is not None:
                    pdf_export.export_pdf(
                        g2_path.with_suffix(".pdf"), chords, fretted_g2, key_estimate, tempo,
                        g2_label, selected_tuning, font_size=args.pdf_font_size
                    )
                pdf_export.export_pdf(
                    bass_tab_path.with_suffix(".pdf"), chords, fretted_bass, key_estimate, tempo,
                    bass_label, bass_tuning_obj, font_size=args.pdf_font_size
                )

            outputs = [str(g1_path)]
            if notes_g2 is not None:
                outputs.append(str(g2_path))
            outputs.append(str(bass_tab_path))
            print(f"\nDone. Tabs written to: {', '.join(outputs)}")

        else:
            print("[1/7] Separating sources with Demucs (htdemucs_6s)...")
            harmonic_path, bass_stem_path = separation.separate(audio_path, work_dir, device=args.device)

            print("[2/7] Transcribing notes with basic-pitch...")
            notes = transcription.transcribe(harmonic_path)
            print(f"       -> {len(notes)} notes detected")

            print("[3/7] Confirming tuning...")
            selected_tuning = tuning.find_tuning(args.tuning)
            suggestion = tuning.suggest_alternate_tuning(notes, selected_tuning)
            if suggestion is not None:
                print(f"       NOTE: {selected_tuning.name} doesn't fully match what's heard.")
                print(f"       Suggestion: {suggestion.suggested.name} "
                      f"(confidence={suggestion.confidence:.2f}). Re-run with "
                      f"--tuning \"{suggestion.suggested.name}\" if that's correct.")
            else:
                print(f"       -> {selected_tuning.name} confirmed")

            print("[4/7] Loading harmonic mix for key/chord analysis...")
            y, sr = librosa.load(harmonic_path, sr=None, mono=True)
            bass_y, bass_sr = librosa.load(bass_stem_path, sr=None, mono=True)

            print("[5/7] Detecting key (chroma + Krumhansl-Schmuckler)...")
            key_estimate = key_detection.detect_key(y, sr)
            print(f"       -> {key_estimate} (correlation={key_estimate.correlation:.2f})")

            print("[6/7] Detecting chords (bass-root + diatonic-key aware, hysteresis-smoothed)...")
            chords, tempo = chord_detection.detect_chords(y, sr, bass_y, bass_sr, key_estimate)
            print(f"       -> {len(chords)} bars, tempo ~{tempo:.1f} BPM")

            print("[7/7] Mapping notes to fretboard and rendering tab...")
            fretted_notes = fretboard.map_notes_to_fretboard(notes, selected_tuning)
            tab_render.write_tab(output_path, chords, fretted_notes, key_estimate, tempo,
                                  audio_path.name, tuning=selected_tuning)

            if args.voices == 2:
                treble_notes, bass_notes = voice_split.split_voices(fretted_notes)
                treble_path = output_path.with_name(f"{output_path.stem}_guitare_aigue.txt")
                bass_path = output_path.with_name(f"{output_path.stem}_guitare_grave.txt")
                treble_strings = "/".join(selected_tuning.string_names[3:])
                bass_strings = "/".join(selected_tuning.string_names[:3])
                treble_label = f"{audio_path.name} (voix aigue {treble_strings} -- heuristique, pas une vraie 2e guitare)"
                bass_label = f"{audio_path.name} (voix grave {bass_strings} -- heuristique, pas une vraie 2e guitare)"
                tab_render.write_tab(treble_path, chords, treble_notes, key_estimate, tempo,
                                      treble_label, tuning=selected_tuning)
                tab_render.write_tab(bass_path, chords, bass_notes, key_estimate, tempo,
                                      bass_label, tuning=selected_tuning)
                print(f"Voice split: {treble_path}, {bass_path}")

                if args.export_pdf:
                    treble_pdf_path = output_path.with_name(f"{output_path.stem}_guitare_aigue.pdf")
                    bass_pdf_path = output_path.with_name(f"{output_path.stem}_guitare_grave.pdf")
                    pdf_export.export_pdf(treble_pdf_path, chords, treble_notes, key_estimate, tempo,
                                           treble_label, selected_tuning, font_size=args.pdf_font_size)
                    pdf_export.export_pdf(bass_pdf_path, chords, bass_notes, key_estimate, tempo,
                                           bass_label, selected_tuning, font_size=args.pdf_font_size)
                    print(f"Voice split PDF: {treble_pdf_path}, {bass_pdf_path}")

            if args.export_midi:
                midi_path = output_path.with_suffix(".mid")
                midi_export.export_midi(midi_path, fretted_notes, tempo)
                print(f"MIDI export: {midi_path}")

            if args.export_pdf:
                pdf_path = output_path.with_suffix(".pdf")
                pdf_export.export_pdf(pdf_path, chords, fretted_notes, key_estimate, tempo,
                                       audio_path.name, selected_tuning, font_size=args.pdf_font_size)
                print(f"PDF export: {pdf_path}")

            print(f"\nDone. Tab written to: {output_path}")

    finally:
        if args.keep_stems:
            stems_dest = output_path.parent / f"{audio_path.stem}_stems"
            src_stems = work_dir / "stems"
            if src_stems.exists():
                if stems_dest.exists():
                    shutil.rmtree(stems_dest)
                shutil.move(str(src_stems), str(stems_dest))
        shutil.rmtree(work_dir, ignore_errors=True)
```

- [ ] **Step 6: Run the full test suite**

```bash
./.venv/bin/python3 -m pytest -v 2>&1 | tail -30
```
Expected: all tests pass.

- [ ] **Step 7: Verify --help includes new flags**

```bash
./.venv/bin/python3 main.py --help 2>&1 | grep -E "multi-guitar|bass-tuning"
```
Expected: both flags appear in the help output.

- [ ] **Step 8: Commit**

```bash
git add main.py tests/test_main_args.py
git commit -m "feat: --multi-guitar mode — guitar 1 (L), guitar 2 (R), bass tabs from a single song"
```

---

## Task 7 (manual smoke test) — Full pipeline run with --multi-guitar

Not automated — requires Demucs + basic-pitch on a real stereo song. Skip if time-constrained; Tasks 1-6 cover all logic with unit tests.

- [ ] **Step 1: Run on a stereo song with two guitars**

```bash
./.venv/bin/python3 main.py "<path/to/song.wav>" \
  --multi-guitar \
  --export-pdf \
  --output /tmp/mg_test_tab.txt
```
Expected:
- Prints 8 progress steps
- Produces `mg_test_tab_guitare1.txt`, `mg_test_tab_guitare2.txt`, `mg_test_tab_basse.txt`
- Produces matching `.pdf` files

- [ ] **Step 2: Inspect outputs**

```bash
head -15 /tmp/mg_test_tab_guitare1.txt
head -5 /tmp/mg_test_tab_basse.txt
```
Expected for bass: 4-line tab with string labels `E|`, `A|`, `D|`, `G|` (not 6 lines).

- [ ] **Step 3: Verify bass PDF**

```bash
open /tmp/mg_test_tab_basse.pdf
```
Expected: 4-string ASCII tab in Courier PDF, portrait A4.
