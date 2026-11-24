# Tuning Detection & Confirmation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add tuning presets, a fingerprint-based "does this tuning actually match what's heard" check, and CLI wiring so `main.py` confirms/suggests a guitar tuning before generating a tab, instead of silently assuming Standard EADGBE.

**Architecture:** Pure-Python addition to the existing `guitar_tab_pipeline` — a new `pipeline/tuning.py` module holds a small catalog of named tunings and a fit-scoring function that checks how many of basic-pitch's transcribed notes can actually be fretted (within `[0, MAX_FRET]`) on a given tuning; notes below a tuning's lowest open string are the key signal (e.g. a recurring low D under a Standard-tuning assumption). `fretboard.py` and `tab_render.py` are parametrized to accept a `Tuning` instead of hardcoding Standard EADGBE, and `main.py` gains a `--tuning` CLI flag plus a printed suggestion when the selected tuning doesn't fit well. This CLI confirmation is a stand-in for the eventual SwiftUI dialog described in the design spec — the Mac app work is a separate, later plan.

**Tech Stack:** Python 3.9 (existing project venv), pytest for unit tests. No new runtime dependencies (librosa/numpy/basic-pitch already installed).

---

## Context for the engineer

- This plan implements the highest-priority differentiator ("accordage vérifié") from the design spec at `docs/superpowers/specs/2026-07-17-mac-ios-tab-app-design.md`.
- The project's `.venv` was created inside a Google Drive folder that has since been renamed/moved. The venv's own `bin/python`/`bin/python3` symlinks still work (they point to the system Command Line Tools Python), but every *installed console-script* wrapper (`bin/pip`, `bin/pytest` if it existed, `bin/demucs`, etc.) has a broken shebang baked in at install time pointing to the old absolute path. **Always invoke tools as `./.venv/bin/python3 -m <tool>` (e.g. `-m pip`, `-m pytest`), never via the bare script** (e.g. `./.venv/bin/pytest`) — the bare scripts will fail with "No such file or directory".
- All commands below assume the working directory is the `guitar_tab_pipeline/` project root (the same directory as `main.py` and `requirements.txt`).
- There is no git repository yet anywhere in this project. Task 1 initializes one, locally only — nothing is pushed anywhere in this plan.

---

### Task 1: Bootstrap dev environment (pytest + local git repo)

**Files:**
- Create: `guitar_tab_pipeline/.gitignore`

- [ ] **Step 1: Install pytest into the existing venv**

Run: `./.venv/bin/python3 -m pip install pytest`
Expected: `Successfully installed ... pytest-8.x.x ...` (iniconfig/pluggy/pygments/tomli may already be present or install alongside it)

- [ ] **Step 2: Verify pytest runs and the existing pipeline modules still import**

Run: `./.venv/bin/python3 -m pytest --version`
Expected: prints a pytest version, e.g. `pytest 8.4.2`

Run: `./.venv/bin/python3 -c "from pipeline import fretboard, tab_render, transcription; print('ok')"`
Expected: prints `ok` (some `WARNING:root:...` / coremltools/scikit-learn version noise from basic-pitch on import is normal and can be ignored)

- [ ] **Step 3: Create `.gitignore`**

```gitignore
.venv/
__pycache__/
*.pyc
.pytest_cache/
```

- [ ] **Step 4: Initialize the local git repo and commit the existing pipeline as a baseline**

```bash
git init
git add .gitignore main.py pipeline requirements.txt install.log run.log
git commit -m "chore: baseline commit of existing guitar_tab_pipeline"
```

Expected: `git status` afterwards shows a clean working tree (only `.venv/` untracked-and-ignored).

---

### Task 2: Tuning catalog

**Files:**
- Create: `pipeline/tuning.py`
- Test: `tests/test_tuning.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_tuning.py
import pytest

from pipeline.tuning import (
    DROP_D,
    STANDARD_E_A_D_G_B_E,
    TUNINGS,
    find_tuning,
)


def test_tunings_catalog_has_seven_entries():
    assert len(TUNINGS) == 7


def test_find_tuning_returns_standard():
    tuning = find_tuning(STANDARD_E_A_D_G_B_E)
    assert tuning.open_string_midi == [40, 45, 50, 55, 59, 64]
    assert tuning.string_names == ["E", "A", "D", "G", "B", "e"]


def test_find_tuning_returns_drop_d():
    tuning = find_tuning(DROP_D)
    assert tuning.open_string_midi == [38, 45, 50, 55, 59, 64]
    assert tuning.string_names == ["D", "A", "D", "G", "B", "e"]


def test_find_tuning_raises_on_unknown_name():
    with pytest.raises(ValueError):
        find_tuning("Nonexistent Tuning")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `./.venv/bin/python3 -m pytest tests/test_tuning.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline.tuning'`

- [ ] **Step 3: Write the implementation**

```python
# pipeline/tuning.py
"""Guitar tuning catalog.

Tunings are represented as open-string MIDI pitches, ordered from the
lowest-pitched string to the highest-pitched string -- the same convention
`fretboard.py` uses for its fretting logic. `MAX_FRET` (the highest fret
position the pipeline will consider when fretting a note) lives here rather
than in `fretboard.py` so that tuning fit-scoring (see the `fit_score`
function added in a later step) does not need to import from `fretboard`,
which avoids a circular import between the two modules.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

MAX_FRET = 15

STANDARD_E_A_D_G_B_E = "Standard EADGBE"
DROP_D = "Drop D"
EB_STANDARD = "Eb Standard"
D_STANDARD = "D Standard"
DROP_C_SHARP = "Drop C#"
OPEN_G = "Open G"
OPEN_D = "Open D"


@dataclass(frozen=True)
class Tuning:
    name: str
    open_string_midi: List[int]  # lowest string to highest string, 6 values
    string_names: List[str]


TUNINGS: List[Tuning] = [
    Tuning(STANDARD_E_A_D_G_B_E, [40, 45, 50, 55, 59, 64], ["E", "A", "D", "G", "B", "e"]),
    Tuning(DROP_D, [38, 45, 50, 55, 59, 64], ["D", "A", "D", "G", "B", "e"]),
    Tuning(EB_STANDARD, [39, 44, 49, 54, 58, 63], ["Eb", "Ab", "Db", "Gb", "Bb", "eb"]),
    Tuning(D_STANDARD, [38, 43, 48, 53, 57, 62], ["D", "G", "C", "F", "A", "d"]),
    Tuning(DROP_C_SHARP, [37, 44, 49, 54, 58, 63], ["C#", "Ab", "Db", "Gb", "Bb", "eb"]),
    Tuning(OPEN_G, [38, 43, 50, 55, 59, 62], ["D", "G", "D", "G", "B", "d"]),
    Tuning(OPEN_D, [38, 45, 50, 54, 57, 62], ["D", "A", "D", "F#", "A", "d"]),
]


def find_tuning(name: str) -> Tuning:
    for tuning in TUNINGS:
        if tuning.name == name:
            return tuning
    raise ValueError(f"Unknown tuning: {name!r}")
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `./.venv/bin/python3 -m pytest tests/test_tuning.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add pipeline/tuning.py tests/test_tuning.py
git commit -m "feat: add guitar tuning catalog"
```

---

### Task 3: Fit-scoring a tuning against transcribed notes

**Files:**
- Modify: `pipeline/tuning.py`
- Test: `tests/test_tuning.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_tuning.py`:

```python
from pipeline.transcription import Note
from pipeline.tuning import fit_score


def _note(pitch, start=0.0, end=0.5):
    return Note(start=start, end=end, pitch=pitch, velocity=0.8)


def test_fit_score_is_one_when_all_notes_fit():
    tuning = find_tuning(STANDARD_E_A_D_G_B_E)
    notes = [_note(40), _note(45), _note(64)]
    assert fit_score(notes, tuning) == 1.0


def test_fit_score_penalizes_notes_below_lowest_open_string():
    tuning = find_tuning(STANDARD_E_A_D_G_B_E)
    notes = [_note(40), _note(38)]  # 38 (D2) is below open low E (40)
    assert fit_score(notes, tuning) == 0.5


def test_fit_score_is_one_for_empty_notes():
    tuning = find_tuning(STANDARD_E_A_D_G_B_E)
    assert fit_score([], tuning) == 1.0
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `./.venv/bin/python3 -m pytest tests/test_tuning.py -v`
Expected: the 3 new tests FAIL with `ImportError: cannot import name 'fit_score'`

- [ ] **Step 3: Write the implementation**

Append to `pipeline/tuning.py` (add `Note` to the imports at the top: `from .transcription import Note`):

```python
def _fits(pitch: int, tuning: Tuning) -> bool:
    return any(0 <= pitch - open_midi <= MAX_FRET for open_midi in tuning.open_string_midi)


def fit_score(notes: List[Note], tuning: Tuning) -> float:
    """Fraction of `notes` that CAN be fretted on `tuning` within [0, MAX_FRET].

    Notes below every string's open pitch (i.e. would need a negative fret)
    are the strongest signal of a mismatched tuning -- e.g. a recurring low
    D under an assumed Standard tuning, where no string can produce it.
    """
    if not notes:
        return 1.0
    fitting = sum(1 for note in notes if _fits(note.pitch, tuning))
    return fitting / len(notes)
```

And add the import at the top of `pipeline/tuning.py`, right after `from typing import List`:

```python
from .transcription import Note
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `./.venv/bin/python3 -m pytest tests/test_tuning.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add pipeline/tuning.py tests/test_tuning.py
git commit -m "feat: score how well a tuning fits a set of transcribed notes"
```

---

### Task 4: Suggesting a better-fitting tuning

**Files:**
- Modify: `pipeline/tuning.py`
- Test: `tests/test_tuning.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_tuning.py`:

```python
from pipeline.tuning import suggest_alternate_tuning


def test_suggest_alternate_tuning_detects_lower_tuning_from_low_notes():
    standard = find_tuning(STANDARD_E_A_D_G_B_E)
    # a riff that repeatedly hits a low D (38), which no string in Standard
    # tuning can produce, alongside notes Standard covers fine
    notes = [_note(38), _note(38), _note(45), _note(50), _note(55), _note(59),
              _note(64), _note(38), _note(45)]
    suggestion = suggest_alternate_tuning(notes, standard)
    assert suggestion is not None
    assert suggestion.suggested.open_string_midi[0] <= 38
    assert suggestion.confidence >= 0.9


def test_suggest_alternate_tuning_returns_none_when_selected_fits_well():
    standard = find_tuning(STANDARD_E_A_D_G_B_E)
    notes = [_note(40), _note(45), _note(50), _note(55), _note(59), _note(64)]
    assert suggest_alternate_tuning(notes, standard) is None


def test_suggest_alternate_tuning_returns_none_when_selected_already_scores_high_enough():
    standard = find_tuning(STANDARD_E_A_D_G_B_E)
    # one low outlier out of ten notes: Standard still scores 0.9, which
    # already meets the confidence bar, so no alternate is even considered
    notes = [_note(38), _note(40), _note(45), _note(50), _note(55), _note(59),
              _note(64), _note(40), _note(45), _note(50)]
    assert suggest_alternate_tuning(notes, standard) is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `./.venv/bin/python3 -m pytest tests/test_tuning.py -v`
Expected: the 3 new tests FAIL with `ImportError: cannot import name 'suggest_alternate_tuning'`

- [ ] **Step 3: Write the implementation**

Change the `from typing import List` line at the top of `pipeline/tuning.py` to:

```python
from typing import List, Optional
```

Then append to `pipeline/tuning.py`:

```python
@dataclass
class TuningSuggestion:
    suggested: Tuning
    confidence: float


def suggest_alternate_tuning(notes: List[Note], selected: Tuning,
                              min_confidence: float = 0.9,
                              min_improvement: float = 0.1) -> Optional[TuningSuggestion]:
    """Return a better-fitting tuning if one clearly explains `notes` better
    than `selected`, else None.

    "Clearly better" means: the candidate scores at least `min_confidence`,
    AND it beats `selected`'s score by at least `min_improvement`. If ties
    occur between candidates, the first one encountered in `TUNINGS` wins --
    this pipeline cannot distinguish tunings that happen to fit the same set
    of notes equally well (e.g. a song that never touches its lowest string
    sounds identical in Drop D and D Standard).
    """
    selected_score = fit_score(notes, selected)
    if selected_score >= min_confidence:
        return None  # selected tuning already explains the notes well

    best: Optional[TuningSuggestion] = None
    for tuning in TUNINGS:
        if tuning.name == selected.name:
            continue
        score = fit_score(notes, tuning)
        if score >= min_confidence and score - selected_score >= min_improvement:
            if best is None or score > best.confidence:
                best = TuningSuggestion(suggested=tuning, confidence=score)
    return best
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `./.venv/bin/python3 -m pytest tests/test_tuning.py -v`
Expected: 10 passed

- [ ] **Step 5: Commit**

```bash
git add pipeline/tuning.py tests/test_tuning.py
git commit -m "feat: suggest a better-fitting tuning from transcribed notes"
```

---

### Task 5: Parametrize fretboard mapping by tuning

**Files:**
- Modify: `pipeline/fretboard.py`
- Test: `tests/test_fretboard.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_fretboard.py
from pipeline.fretboard import map_notes_to_fretboard
from pipeline.transcription import Note
from pipeline.tuning import DROP_D, STANDARD_E_A_D_G_B_E, find_tuning


def _note(pitch, start=0.0, end=0.5):
    return Note(start=start, end=end, pitch=pitch, velocity=0.8)


def test_defaults_to_standard_tuning():
    fretted = map_notes_to_fretboard([_note(40)])
    assert len(fretted) == 1
    assert fretted[0].string == 0
    assert fretted[0].fret == 0


def test_low_note_is_dropped_under_standard_tuning():
    fretted = map_notes_to_fretboard([_note(38)], find_tuning(STANDARD_E_A_D_G_B_E))
    assert fretted == []


def test_low_note_is_fretted_under_drop_d_tuning():
    fretted = map_notes_to_fretboard([_note(38)], find_tuning(DROP_D))
    assert len(fretted) == 1
    assert fretted[0].string == 0
    assert fretted[0].fret == 0
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `./.venv/bin/python3 -m pytest tests/test_fretboard.py -v`
Expected: `test_low_note_is_dropped_under_standard_tuning` and `test_low_note_is_fretted_under_drop_d_tuning` FAIL with `TypeError: map_notes_to_fretboard() takes 1 positional argument but 2 were given`

- [ ] **Step 3: Rewrite `pipeline/fretboard.py`**

```python
"""Step 5: map detected notes to (string, fret) positions on a guitar neck
for a given tuning.

Heuristic (intentionally simple, see module-level limitation below):
for each note, or each near-simultaneous group of notes (a "chord grasp"),
try every string that can produce the pitch within [0, MAX_FRET] and pick
the LOWEST fret available, breaking ties toward the lower (thicker) string.
Within a simultaneous group, a string can only be used once, so notes are
assigned string-by-string, highest pitch first, removing used strings as we
go.

Known limitations:
- This does NOT model real playability: it ignores physical hand span,
  barre chords, open-string ringing, and idiomatic fingerings. A real
  guitarist would frequently choose a different (often higher-position)
  fingering for musical or ergonomic reasons.
- Notes outside the guitar's range for the given tuning (below the lowest
  open string, or above MAX_FRET on the highest string) are silently
  dropped.
- Chords with more simultaneous notes than available open strings (>6, or
  >remaining strings after low-fret assignment) will have the excess notes
  dropped rather than re-voiced.
- Grouping "simultaneous" notes uses a fixed time tolerance (CHORD_TOLERANCE)
  which can incorrectly split a slightly-arpeggiated strum into separate
  groups, or merge two quick separate notes into one "chord".
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from .transcription import Note
from .tuning import MAX_FRET, STANDARD_E_A_D_G_B_E, Tuning, find_tuning

CHORD_TOLERANCE = 0.05  # seconds; notes starting within this window are one "grasp"


@dataclass
class FrettedNote:
    string: int  # 0 = lowest string ... 5 = highest string
    fret: int
    start: float
    end: float
    pitch: int


def _fret_options(pitch: int, tuning: Tuning) -> List[tuple]:
    """All (string, fret) pairs that can produce `pitch` on `tuning`, lowest fret first."""
    options = []
    for string_idx, open_midi in enumerate(tuning.open_string_midi):
        fret = pitch - open_midi
        if 0 <= fret <= MAX_FRET:
            options.append((string_idx, fret))
    options.sort(key=lambda sf: (sf[1], sf[0]))  # lowest fret, then lower string
    return options


def _group_by_onset(notes: List[Note]) -> List[List[Note]]:
    groups: List[List[Note]] = []
    for note in sorted(notes, key=lambda n: n.start):
        if groups and note.start - groups[-1][0].start <= CHORD_TOLERANCE:
            groups[-1].append(note)
        else:
            groups.append([note])
    return groups


def map_notes_to_fretboard(notes: List[Note], tuning: Optional[Tuning] = None) -> List[FrettedNote]:
    if tuning is None:
        tuning = find_tuning(STANDARD_E_A_D_G_B_E)
    fretted: List[FrettedNote] = []
    for group in _group_by_onset(notes):
        used_strings = set()
        # Assign highest pitches first: they have fewer valid strings/frets,
        # so giving them first pick reduces collisions.
        for note in sorted(group, key=lambda n: -n.pitch):
            chosen: Optional[tuple] = None
            for string_idx, fret in _fret_options(note.pitch, tuning):
                if string_idx not in used_strings:
                    chosen = (string_idx, fret)
                    break
            if chosen is None:
                continue  # out of range or no free string left; note dropped
            string_idx, fret = chosen
            used_strings.add(string_idx)
            fretted.append(FrettedNote(
                string=string_idx, fret=fret,
                start=note.start, end=note.end, pitch=note.pitch,
            ))
    fretted.sort(key=lambda fn: fn.start)
    return fretted
```

This removes the module-level `OPEN_STRING_MIDI`, `STRING_NAMES`, and `MAX_FRET` constants (confirmed via `grep -rn "OPEN_STRING_MIDI\|STRING_NAMES\|MAX_FRET" pipeline/*.py main.py` that only `fretboard.py` and `tab_render.py` reference them — `tab_render.py` is fixed in Task 6).

- [ ] **Step 4: Run the tests to verify they pass**

Run: `./.venv/bin/python3 -m pytest tests/test_fretboard.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add pipeline/fretboard.py tests/test_fretboard.py
git commit -m "feat: parametrize fretboard mapping by tuning"
```

---

### Task 6: Parametrize tab rendering by tuning

**Files:**
- Modify: `pipeline/tab_render.py`
- Test: `tests/test_tab_render.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_tab_render.py
from pipeline.chord_detection import ChordSegment
from pipeline.key_detection import KeyEstimate
from pipeline.tab_render import render_tab
from pipeline.tuning import DROP_D, STANDARD_E_A_D_G_B_E, find_tuning


def _bar(index, start, end, label="Em"):
    return ChordSegment(bar_index=index, start=start, end=end, label=label)


def test_header_reports_selected_tuning_name():
    bars = [_bar(0, 0.0, 2.0)]
    key = KeyEstimate(tonic="E", mode="minor", correlation=0.9)
    text = render_tab(bars, [], key, 120.0, "song.wav", find_tuning(STANDARD_E_A_D_G_B_E))
    assert "# Tuning: Standard EADGBE" in text


def test_string_row_labels_follow_the_tuning():
    bars = [_bar(0, 0.0, 2.0)]
    key = KeyEstimate(tonic="D", mode="major", correlation=0.9)
    text = render_tab(bars, [], key, 120.0, "song.wav", find_tuning(DROP_D))
    lines = text.splitlines()
    assert any(line.startswith("D|") for line in lines)  # lowest string relabeled from E to D
    assert any(line.startswith("e|") for line in lines)  # highest string unchanged
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `./.venv/bin/python3 -m pytest tests/test_tab_render.py -v`
Expected: FAIL with `TypeError: render_tab() takes from 5 to 6 positional arguments but 7 were given`

- [ ] **Step 3: Modify `pipeline/tab_render.py`**

Change the import line:

```python
from .chord_detection import ChordSegment
from .fretboard import FrettedNote
from .key_detection import KeyEstimate
from .tuning import STANDARD_E_A_D_G_B_E, Tuning, find_tuning
```

Change the `render_tab` signature and body (replace the whole function):

```python
def render_tab(bars: List[ChordSegment], notes: List[FrettedNote],
               key_estimate: KeyEstimate, tempo: float,
               source_name: str, tuning: Tuning = None, bars_per_line: int = 4) -> str:
    if tuning is None:
        tuning = find_tuning(STANDARD_E_A_D_G_B_E)
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
        # find the bar this note's onset falls into
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
            grid = _new_bar_grid()
            for note in notes_by_bar[line_start + i]:
                _place_note(grid, note, bar)
            grids.append(grid)

        for row_idx in range(6):
            row_str = tuning.string_names[5 - row_idx] + "|"
            for grid in grids:
                cells = [cell.ljust(CELL_WIDTH, "-") for cell in grid[row_idx]]
                row_str += "".join(cells) + "|"
            out.append(row_str)

        out.append("")

    return "\n".join(out)
```

Change `write_tab` to accept and forward `tuning`:

```python
def write_tab(path: Path, bars: List[ChordSegment], notes: List[FrettedNote],
              key_estimate: KeyEstimate, tempo: float, source_name: str,
              tuning: Tuning = None) -> None:
    text = render_tab(bars, notes, key_estimate, tempo, source_name, tuning)
    path.write_text(text, encoding="utf-8")
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `./.venv/bin/python3 -m pytest tests/test_tab_render.py -v`
Expected: 2 passed

- [ ] **Step 5: Run the full test suite to check for regressions**

Run: `./.venv/bin/python3 -m pytest -v`
Expected: all tests across `tests/test_tuning.py`, `tests/test_fretboard.py`, `tests/test_tab_render.py` pass

- [ ] **Step 6: Commit**

```bash
git add pipeline/tab_render.py tests/test_tab_render.py
git commit -m "feat: parametrize tab rendering by tuning"
```

---

### Task 7: Wire `--tuning` into the CLI

**Files:**
- Modify: `main.py`
- Test: `tests/test_main_args.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_main_args.py
import sys

import pytest

from main import parse_args


def test_tuning_flag_defaults_to_standard(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["main.py", "song.wav"])
    args = parse_args()
    assert args.tuning == "Standard EADGBE"


def test_tuning_flag_accepts_known_preset(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["main.py", "song.wav", "--tuning", "Drop D"])
    args = parse_args()
    assert args.tuning == "Drop D"


def test_tuning_flag_rejects_unknown_preset(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["main.py", "song.wav", "--tuning", "Nope"])
    with pytest.raises(SystemExit):
        parse_args()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `./.venv/bin/python3 -m pytest tests/test_main_args.py -v`
Expected: FAIL — `test_tuning_flag_defaults_to_standard` and `test_tuning_flag_accepts_known_preset` fail with `AttributeError: 'Namespace' object has no attribute 'tuning'`

- [ ] **Step 3: Modify `main.py`**

Add `tuning` to the pipeline import line:

```python
from pipeline import chord_detection, fretboard, key_detection, midi_export, separation, tab_render, transcription, tuning, voice_split
```

Add the CLI flag inside `parse_args()`, right after the `--voices` argument:

```python
    parser.add_argument("--tuning", default=tuning.STANDARD_E_A_D_G_B_E,
                         choices=[t.name for t in tuning.TUNINGS],
                         help="Guitar tuning to assume before fretboard mapping "
                              "(default: %(default)s)")
```

Replace the body of `main()` from the `try:` block onward with:

```python
    try:
        print("[1/7] Separating sources with Demucs (htdemucs_6s)...")
        harmonic_path = separation.separate(audio_path, work_dir, device=args.device)

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

        print("[5/7] Detecting key (chroma + Krumhansl-Schmuckler)...")
        key_estimate = key_detection.detect_key(y, sr)
        print(f"       -> {key_estimate} (correlation={key_estimate.correlation:.2f})")

        print("[6/7] Detecting chords (beat-synchronous chroma templates)...")
        chords = chord_detection.detect_chords(y, sr)
        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
        tempo = float(np.asarray(tempo).reshape(-1)[0])
        print(f"       -> {len(chords)} bars, tempo ~{tempo:.1f} BPM")

        print("[7/7] Mapping notes to fretboard and rendering tab...")
        fretted_notes = fretboard.map_notes_to_fretboard(notes, selected_tuning)
        tab_render.write_tab(output_path, chords, fretted_notes, key_estimate, tempo,
                              audio_path.name, tuning=selected_tuning)

        if args.voices == 2:
            treble_notes, bass_notes = voice_split.split_voices(fretted_notes)
            treble_path = output_path.with_name(f"{output_path.stem}_guitare_aigue.txt")
            bass_path = output_path.with_name(f"{output_path.stem}_guitare_grave.txt")
            tab_render.write_tab(treble_path, chords, treble_notes, key_estimate, tempo,
                                  f"{audio_path.name} (voix aigue G/B/e -- heuristique, pas une vraie 2e guitare)",
                                  tuning=selected_tuning)
            tab_render.write_tab(bass_path, chords, bass_notes, key_estimate, tempo,
                                  f"{audio_path.name} (voix grave E/A/D -- heuristique, pas une vraie 2e guitare)",
                                  tuning=selected_tuning)
            print(f"Voice split: {treble_path}, {bass_path}")

        if args.export_midi:
            midi_path = output_path.with_suffix(".mid")
            midi_export.export_midi(midi_path, fretted_notes, tempo)
            print(f"MIDI export: {midi_path}")

        print(f"\nDone. Tab written to: {output_path}")

    finally:
        if args.keep_stems:
            stems_dest = audio_path.parent / f"{audio_path.stem}_stems"
            src_stems = work_dir / "stems"
            if src_stems.exists():
                if stems_dest.exists():
                    shutil.rmtree(stems_dest)
                shutil.move(str(src_stems), str(stems_dest))
        shutil.rmtree(work_dir, ignore_errors=True)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `./.venv/bin/python3 -m pytest tests/test_main_args.py -v`
Expected: 3 passed

- [ ] **Step 5: Run the full test suite**

Run: `./.venv/bin/python3 -m pytest -v`
Expected: all 18 tests pass (10 in `tests/test_tuning.py`, 3 in `tests/test_fretboard.py`, 2 in `tests/test_tab_render.py`, 3 in `tests/test_main_args.py`)

- [ ] **Step 6: Verify the CLI help text shows the new flag**

Run: `./.venv/bin/python3 main.py --help`
Expected: output includes a `--tuning` option listing all 7 tuning names as choices

- [ ] **Step 7: Commit**

```bash
git add main.py tests/test_main_args.py
git commit -m "feat: confirm tuning via --tuning flag before fretboard mapping"
```

---

### Task 8 (optional manual smoke test): Full pipeline run on real audio

This is not part of the automated test suite — it re-runs the full, slow (Demucs + basic-pitch) pipeline to confirm the wiring works end-to-end on real audio, not just unit-level. Skip if time-constrained; Tasks 1-7's automated tests already cover the new logic.

- [ ] **Step 1: Re-run the pipeline on the song already used in this project, in Standard tuning**

Run (from the parent `Village_claire-TIMEBENT` directory, adjusting the path to wherever the source `.wav` lives):
```bash
cd notara
./.venv/bin/python3 main.py "../Village_claire-TIMEBENT/GOOD - Can Our Time Be Bent (village clair).wav" --output /tmp/smoke_test_tab.txt
```
Expected: completes with `[3/7] Confirming tuning...` printing either a confirmation or a suggestion, and finishes with `Done. Tab written to: /tmp/smoke_test_tab.txt`.

- [ ] **Step 2: Inspect the header of the output**

Run: `head -5 /tmp/smoke_test_tab.txt`
Expected: a `# Tuning: Standard EADGBE` line is present (or whatever tuning was selected).
