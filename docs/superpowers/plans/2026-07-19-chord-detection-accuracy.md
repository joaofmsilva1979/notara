# Chord Detection Accuracy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `pipeline/chord_detection.py` noticeably more accurate by constraining the chord root with the (currently discarded) separated bass stem, nudging ambiguous bars toward the detected song key, and smoothing incoherent bar-to-bar flip-flopping — while fixing a redundant/inconsistent tempo computation found along the way.

**Architecture:** `pipeline/separation.py` starts returning the already-produced-but-discarded bass stem path alongside the harmonic mix. `pipeline/chord_detection.py` is refactored into small pure functions (chroma vector in, decision out) so the new logic is unit-testable with synthetic chroma vectors, no real audio needed: a bass-clarity check that can force a bar's chord root, a diatonic-key soft-scoring bonus for ambiguous bars, and a bar-to-bar hysteresis pass that only touches bars whose root wasn't forced by the bass. `main.py` is updated to thread the bass audio and detected key into `detect_chords`, and to stop computing tempo twice.

**Tech Stack:** Python 3.9, pytest, numpy, librosa (existing project stack — no new dependencies).

---

## Context for the engineer

- This plan implements `docs/superpowers/specs/2026-07-19-chord-detection-accuracy-design.md` in full.
- Working directory for all commands: `guitar_tab_pipeline/` project root (same directory as `main.py`).
- Environment gotcha (same as before): always invoke tools as `./.venv/bin/python3 -m <tool>` (e.g. `-m pytest`), never a bare script — the venv's console-script wrappers have broken shebangs from an earlier folder rename.
- **Naming collision to watch for in Task 7:** `main.py` already has a local variable named `bass_path` inside the `if args.voices == 2:` block (the *output tab file path* for the bass-register split, e.g. `..._guitare_grave.txt`). `separation.separate()`'s new second return value (the Demucs-separated *bass audio stem*) must be named differently — this plan uses `bass_stem_path` for it. Do not name it `bass_path`, that would silently collide with the existing variable in the same function scope.
- `pipeline/key_detection.py` has no dependency on `pipeline/chord_detection.py`, so `chord_detection.py` importing `KeyEstimate` from `.key_detection` introduces no circular import.
- `chord_detection.py` already has `from __future__ import annotations` at the top, so built-in generic types like `set[int]` can be used directly in type hints without importing `typing.Set`.

---

### Task 1: `separation.py` also returns the bass stem path

**Files:**
- Modify: `pipeline/separation.py`

- [ ] **Step 1: Update the module docstring and `separate()`'s return type/behavior**

Change the docstring's first paragraph from:
```
Uses the 6-stem model (htdemucs_6s), which has a dedicated "guitar" stem
in addition to drums/bass/vocals/piano/other. We combine guitar + other
into a single "harmonic" mix and discard drums/bass/vocals.
```
to:
```
Uses the 6-stem model (htdemucs_6s), which has a dedicated "guitar" stem
in addition to drums/bass/vocals/piano/other. We combine guitar + other
into a single "harmonic" mix (for transcription and key detection) and
also return the separated bass stem on its own (used by chord_detection.py
to constrain the chord root). Drums/vocals/piano are still discarded.
```

Change `separate()`'s signature and body from:
```python
def separate(audio_path: Path, work_dir: Path, device: str = "cpu") -> Path:
    """Run Demucs and return the path to a combined guitar+other wav."""
    out_dir = work_dir / "stems"
    out_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable, "-m", "demucs",
        "-n", DEMUCS_MODEL,
        "-d", device,
        "-o", str(out_dir),
        str(audio_path),
    ]
    subprocess.run(cmd, check=True)

    track_name = audio_path.stem
    stem_dir = out_dir / DEMUCS_MODEL / track_name
    if not stem_dir.exists():
        raise FileNotFoundError(f"Demucs did not produce expected output at {stem_dir}")

    return _combine_stems(stem_dir, work_dir)
```
to:
```python
def separate(audio_path: Path, work_dir: Path, device: str = "cpu") -> tuple[Path, Path]:
    """Run Demucs and return (harmonic_mix_path, bass_stem_path)."""
    out_dir = work_dir / "stems"
    out_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable, "-m", "demucs",
        "-n", DEMUCS_MODEL,
        "-d", device,
        "-o", str(out_dir),
        str(audio_path),
    ]
    subprocess.run(cmd, check=True)

    track_name = audio_path.stem
    stem_dir = out_dir / DEMUCS_MODEL / track_name
    if not stem_dir.exists():
        raise FileNotFoundError(f"Demucs did not produce expected output at {stem_dir}")

    bass_stem_path = stem_dir / "bass.wav"
    if not bass_stem_path.exists():
        raise FileNotFoundError(f"Demucs did not produce a bass stem at {bass_stem_path}")

    harmonic_path = _combine_stems(stem_dir, work_dir)
    return harmonic_path, bass_stem_path
```

(Leave `_combine_stems` itself untouched — only `separate()`'s signature, return value, and docstring change.)

- [ ] **Step 2: Manually verify the change is self-consistent**

There is no existing unit test for `separation.py` (it shells out to Demucs, like `transcription.py` needs basic-pitch — neither has unit tests in this codebase, by necessity). Instead, verify by reading:

Run: `grep -n "def separate" -A 25 pipeline/separation.py`
Expected: the function now ends with `return harmonic_path, bass_stem_path` and the signature reads `-> tuple[Path, Path]`.

Run: `./.venv/bin/python3 -c "import ast; ast.parse(open('pipeline/separation.py').read())"`
Expected: no output (confirms the file is still valid Python syntax).

- [ ] **Step 3: Commit**

```bash
git add pipeline/separation.py
git commit -m "feat: also return the separated bass stem path from separation.separate"
```

---

### Task 2: chord_detection.py — thresholds, `BarResult`, and bass-root clarity check

**Files:**
- Modify: `pipeline/chord_detection.py`
- Test: `tests/test_chord_detection.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_chord_detection.py
import numpy as np

from pipeline.chord_detection import _bass_root_pitch_class


def test_bass_root_pitch_class_detects_a_clear_single_note():
    # All energy in bin 9 (A) -- an unambiguous, sustained bass note
    vec = np.zeros(12)
    vec[9] = 1.0
    assert _bass_root_pitch_class(vec) == 9


def test_bass_root_pitch_class_returns_none_for_a_near_uniform_vector():
    # Energy spread evenly across all 12 bins -- no single note dominates
    vec = np.full(12, 1.0 / 12)
    assert _bass_root_pitch_class(vec) is None


def test_bass_root_pitch_class_returns_none_for_silence():
    vec = np.zeros(12)
    assert _bass_root_pitch_class(vec) is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `./.venv/bin/python3 -m pytest tests/test_chord_detection.py -v`
Expected: FAIL with `ImportError: cannot import name '_bass_root_pitch_class' from 'pipeline.chord_detection'`

- [ ] **Step 3: Add the constants, `BarResult`, and `_bass_root_pitch_class` to `pipeline/chord_detection.py`**

Add these imports at the top (replace the existing `from typing import List` line):
```python
from typing import List, Optional
```

Add this constant block right after `BEATS_PER_BAR = 4  # assumes 4/4 time (see module docstring)`:
```python
# Fraction of a bar's bass chroma energy that must be concentrated in a single
# pitch class for that pitch class to be treated as a forced chord root.
# Heuristic/tunable, like CHORD_TOLERANCE elsewhere in this pipeline -- not
# derived from any formal model.
BASS_CLARITY_THRESHOLD = 0.35

# Additive score bonus (on the [0, 1] cosine-similarity scale) given to a
# chord template whose root is diatonic to the detected song key, applied
# only when the bass didn't give a clear/forced root for that bar.
DIATONIC_BONUS = 0.03

# Maximum score gap (cosine-similarity scale) for hysteresis smoothing to
# keep the previous bar's label instead of switching to the current bar's
# own (different) winning label.
HYSTERESIS_MARGIN = 0.05
```

Add this dataclass right after the `ChordSegment` dataclass:
```python
@dataclass
class BarResult:
    label: str
    score: float
    root_forced: bool
    chroma: np.ndarray
```

Add this function right after `_build_templates`/`_TEMPLATES` (before `_best_chord`):
```python
def _bass_root_pitch_class(bass_chroma_vec: np.ndarray, threshold: float = BASS_CLARITY_THRESHOLD) -> Optional[int]:
    """Return the dominant pitch class (0-11) if `bass_chroma_vec` is
    concentrated enough on one bin to trust as a forced chord root, else None
    (bass silent, ambiguous, or playing a moving/walking line for this bar).
    """
    total = float(np.sum(bass_chroma_vec))
    if total <= 0:
        return None
    fraction = float(np.max(bass_chroma_vec)) / total
    if fraction < threshold:
        return None
    return int(np.argmax(bass_chroma_vec))
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `./.venv/bin/python3 -m pytest tests/test_chord_detection.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add pipeline/chord_detection.py tests/test_chord_detection.py
git commit -m "feat: add bass-root clarity check to chord detection"
```

---

### Task 3: `_score_label` and root-restricted/diatonic-biased `_best_chord`

**Files:**
- Modify: `pipeline/chord_detection.py`
- Test: `tests/test_chord_detection.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_chord_detection.py`:

```python
import pytest

from pipeline.chord_detection import _TEMPLATES, _best_chord, _score_label


def test_score_label_scores_a_perfect_match_as_one():
    c_template = next(t for root, label, t in _TEMPLATES if label == "C")
    assert _score_label(c_template, "C") == pytest.approx(1.0)


def test_score_label_raises_on_unknown_label():
    with pytest.raises(ValueError):
        _score_label(np.zeros(12), "Not A Real Chord")


def test_best_chord_with_forced_root_only_searches_that_root():
    # A vector shaped exactly like a C major chord (root 0) -- with no
    # constraint this would clearly win as "C". Forcing root=7 (G) must
    # restrict the search to G's 5 templates regardless of fit quality.
    c_major_vec = np.zeros(12)
    c_major_vec[0] = 1.0   # C
    c_major_vec[4] = 0.8   # E
    c_major_vec[7] = 1.0   # G
    label, _score = _best_chord(c_major_vec, forced_root=7)
    assert label.startswith("G")  # G, Gm, G7, Gmaj7, or Gm7 -- never C-rooted


def test_best_chord_diatonic_bonus_does_not_override_a_clear_winner():
    # A pure, unambiguous F# major shape (root 6). "F#" isn't in this
    # (deliberately non-musical) diatonic set, but the bonus (0.03) is far
    # too small to make any bonused template beat F#'s own ~1.0 self-match.
    fsharp_template = next(t for root, label, t in _TEMPLATES if label == "F#")
    label, _score = _best_chord(fsharp_template, diatonic_roots={0, 2, 4, 5, 7, 9, 11})
    assert label == "F#"


def test_best_chord_diatonic_bonus_breaks_a_genuine_tie_against_a_non_diatonic_root():
    # For any two unit template vectors A, B: dot(A+B, A) == dot(A+B, B), by
    # symmetry of the dot product. So scoring their sum against "C" and
    # against "Am" always gives an EXACT tie on raw score, regardless of
    # which two templates are chosen -- this doesn't depend on knowing the
    # full 60-template landscape.
    c_template = next(t for root, label, t in _TEMPLATES if label == "C")
    am_template = next(t for root, label, t in _TEMPLATES if label == "Am")
    tied_vec = c_template + am_template
    assert _score_label(tied_vec, "C") == pytest.approx(_score_label(tied_vec, "Am"))

    # With Am's root (9) diatonic and C's root (0) not, Am's score gets the
    # bonus while C's doesn't -- so Am now strictly beats C. Since they were
    # exactly tied before the bonus, C can never be the overall winner here
    # (something else might beat Am too, but never C, which Am now
    # strictly dominates).
    label, _score = _best_chord(tied_vec, diatonic_roots={9})
    assert label != "C"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `./.venv/bin/python3 -m pytest tests/test_chord_detection.py -v`
Expected: the 5 new tests FAIL — `test_score_label_*` with `ImportError: cannot import name '_score_label'`, and the `_best_chord` tests with a `TypeError` (unexpected keyword argument `forced_root`/`diatonic_roots`) since `_best_chord` doesn't accept those yet, and because it currently returns a plain string rather than a `(label, score)` tuple.

- [ ] **Step 3: Rewrite `_build_templates`/`_TEMPLATES`/`_best_chord`, and add `_score_label`**

Replace `_build_templates`:
```python
def _build_templates() -> List[tuple]:
    templates = []
    for root in range(12):
        for suffix, intervals in CHORD_TYPES:
            vec = np.zeros(12)
            for i, interval in enumerate(intervals):
                # root and fifth weighted slightly higher than 3rd/7th
                weight = 1.0 if i in (0, len(intervals) - 1) else 0.8
                vec[(root + interval) % 12] = weight
            label = f"{NOTE_NAMES[root]}{suffix}"
            templates.append((root, label, vec / np.linalg.norm(vec)))
    return templates


_TEMPLATES = _build_templates()  # List[Tuple[int, str, np.ndarray]] = (root_pitch_class, label, template_vector)
```
(Only change from before: each tuple now also carries the template's root pitch class as its first element.)

Add this new function right after `_TEMPLATES`:
```python
def _score_label(chroma_vec: np.ndarray, label: str) -> float:
    """Cosine similarity between `chroma_vec` and the named chord template."""
    norm = np.linalg.norm(chroma_vec)
    if norm == 0:
        return 0.0
    normalized = chroma_vec / norm
    for _root, template_label, template in _TEMPLATES:
        if template_label == label:
            return float(np.dot(normalized, template))
    raise ValueError(f"Unknown chord label: {label!r}")
```

Replace `_best_chord` entirely:
```python
def _best_chord(chroma_vec: np.ndarray, forced_root: Optional[int] = None,
                 diatonic_roots: Optional[set[int]] = None) -> tuple[str, float]:
    norm = np.linalg.norm(chroma_vec)
    if norm == 0:
        return "N.C.", 0.0  # no chord / silence
    normalized = chroma_vec / norm
    best_label, best_score = "N.C.", -1.0
    for root, label, template in _TEMPLATES:
        if forced_root is not None and root != forced_root:
            continue
        score = float(np.dot(normalized, template))
        if forced_root is None and diatonic_roots is not None and root in diatonic_roots:
            score += DIATONIC_BONUS
        if score > best_score:
            best_label, best_score = label, score
    return best_label, best_score
```

(Note: `_best_chord`'s return type changes from `str` to `tuple[str, float]` — this is fixed up at every call site in Task 6, since `detect_chords` is the only caller.)

- [ ] **Step 4: Run the tests to verify they pass**

Run: `./.venv/bin/python3 -m pytest tests/test_chord_detection.py -v`
Expected: 8 passed.

Note: `detect_chords`'s own internal call — `label = _best_chord(bar_chroma)`, unpacked as a single string — is now inconsistent with `_best_chord`'s new `(label, score)` return type. This is a real, temporary inconsistency, but it does NOT show up as a test failure right now: no existing test (in this file or any other) calls `detect_chords()` itself — it's integration-level and untested at the unit level both before and after this task (see Task 6's note on this). It's fixed in Task 6, which rewrites `detect_chords` entirely.

- [ ] **Step 5: Commit**

```bash
git add pipeline/chord_detection.py tests/test_chord_detection.py
git commit -m "feat: support root-restricted and diatonic-biased chord template matching"
```

---

### Task 4: `_diatonic_roots(key_estimate)`

**Files:**
- Modify: `pipeline/chord_detection.py`
- Test: `tests/test_chord_detection.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_chord_detection.py`:

```python
from pipeline.chord_detection import _diatonic_roots
from pipeline.key_detection import KeyEstimate


def test_diatonic_roots_for_c_major():
    key = KeyEstimate(tonic="C", mode="major", correlation=0.9)
    assert _diatonic_roots(key) == {0, 2, 4, 5, 7, 9, 11}


def test_diatonic_roots_for_a_minor():
    key = KeyEstimate(tonic="A", mode="minor", correlation=0.9)
    # A natural minor uses the same 7 pitch classes as its relative major
    # (C major) -- {A, B, C, D, E, F, G} = {9, 11, 0, 2, 4, 5, 7} -- which is
    # a useful sanity check that the interval math is right.
    assert _diatonic_roots(key) == {0, 2, 4, 5, 7, 9, 11}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `./.venv/bin/python3 -m pytest tests/test_chord_detection.py -v`
Expected: the 2 new tests FAIL with `ImportError: cannot import name '_diatonic_roots'`

- [ ] **Step 3: Add `_diatonic_roots` to `pipeline/chord_detection.py`**

Add `from .key_detection import KeyEstimate` to the imports at the top of the file (after the `numpy` import).

Add this constant block right after the `HYSTERESIS_MARGIN` constant added in Task 2:
```python
MAJOR_SCALE_INTERVALS = [0, 2, 4, 5, 7, 9, 11]
MINOR_SCALE_INTERVALS = [0, 2, 3, 5, 7, 8, 10]  # natural minor
```

Add this function right after `_bass_root_pitch_class`:
```python
def _diatonic_roots(key_estimate: KeyEstimate) -> set[int]:
    """The 7 scale-degree root pitch classes for `key_estimate`'s tonic/mode."""
    tonic_index = NOTE_NAMES.index(key_estimate.tonic)
    intervals = MAJOR_SCALE_INTERVALS if key_estimate.mode == "major" else MINOR_SCALE_INTERVALS
    return {(tonic_index + interval) % 12 for interval in intervals}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `./.venv/bin/python3 -m pytest tests/test_chord_detection.py -v`
Expected: 10 passed

- [ ] **Step 5: Commit**

```bash
git add pipeline/chord_detection.py tests/test_chord_detection.py
git commit -m "feat: compute diatonic root set from the detected song key"
```

---

### Task 5: `_smooth_labels` (hysteresis)

**Files:**
- Modify: `pipeline/chord_detection.py`
- Test: `tests/test_chord_detection.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_chord_detection.py`:

```python
from pipeline.chord_detection import BarResult, HYSTERESIS_MARGIN, _smooth_labels


def test_smooth_labels_pulls_an_isolated_ambiguous_bar_to_match_its_neighbors():
    c_template = next(t for root, label, t in _TEMPLATES if label == "C")
    am_template = next(t for root, label, t in _TEMPLATES if label == "Am")
    tied_chroma = c_template + am_template
    am_score = _score_label(tied_chroma, "Am")

    bars = [
        BarResult(label="C", score=1.0, root_forced=False, chroma=c_template),
        BarResult(label="Am", score=am_score, root_forced=False, chroma=tied_chroma),
        BarResult(label="C", score=1.0, root_forced=False, chroma=c_template),
    ]
    assert _smooth_labels(bars) == ["C", "C", "C"]


def test_smooth_labels_never_changes_a_root_forced_bar():
    c_template = next(t for root, label, t in _TEMPLATES if label == "C")
    am_template = next(t for root, label, t in _TEMPLATES if label == "Am")
    tied_chroma = c_template + am_template
    am_score = _score_label(tied_chroma, "Am")

    bars = [
        BarResult(label="C", score=1.0, root_forced=False, chroma=c_template),
        BarResult(label="Am", score=am_score, root_forced=True, chroma=tied_chroma),
        BarResult(label="C", score=1.0, root_forced=False, chroma=c_template),
    ]
    assert _smooth_labels(bars) == ["C", "Am", "C"]


def test_smooth_labels_keeps_a_clearly_dominant_bar():
    # C and F# major triads share no pitch classes at all (disjoint support),
    # so their raw cosine similarity is exactly 0 -- a gap of 1.0, far above
    # HYSTERESIS_MARGIN, so F# must never be smoothed away here.
    c_template = next(t for root, label, t in _TEMPLATES if label == "C")
    fsharp_template = next(t for root, label, t in _TEMPLATES if label == "F#")

    bars = [
        BarResult(label="C", score=1.0, root_forced=False, chroma=c_template),
        BarResult(label="F#", score=1.0, root_forced=False, chroma=fsharp_template),
    ]
    assert _smooth_labels(bars) == ["C", "F#"]


def test_smooth_labels_never_alters_the_first_bar():
    c_template = next(t for root, label, t in _TEMPLATES if label == "C")
    bars = [BarResult(label="C", score=1.0, root_forced=False, chroma=c_template)]
    assert _smooth_labels(bars) == ["C"]


def test_smooth_labels_handles_empty_input():
    assert _smooth_labels([]) == []
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `./.venv/bin/python3 -m pytest tests/test_chord_detection.py -v`
Expected: the 5 new tests FAIL with `ImportError: cannot import name '_smooth_labels'` (and `BarResult` already exists from Task 2, so only `_smooth_labels` is missing)

- [ ] **Step 3: Add `_smooth_labels` to `pipeline/chord_detection.py`**

Add this function right after `_best_chord`:
```python
def _smooth_labels(bar_results: List[BarResult], margin: float = HYSTERESIS_MARGIN) -> List[str]:
    """Hysteresis pass: for each bar whose root wasn't forced by the bass and
    whose label differs from the previous (already-smoothed) bar's label, keep
    the previous label instead if it scores within `margin` of this bar's own
    winning score against this bar's own chroma. Bars with `root_forced=True`
    are never altered -- bass evidence takes priority over smoothing. The
    first bar has no predecessor, so it's never altered either.
    """
    if not bar_results:
        return []
    labels = [bar_results[0].label]
    for i in range(1, len(bar_results)):
        current = bar_results[i]
        previous_label = labels[i - 1]
        if current.root_forced or current.label == previous_label or previous_label == "N.C.":
            labels.append(current.label)
            continue
        previous_label_score_here = _score_label(current.chroma, previous_label)
        if current.score - previous_label_score_here <= margin:
            labels.append(previous_label)
        else:
            labels.append(current.label)
    return labels
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `./.venv/bin/python3 -m pytest tests/test_chord_detection.py -v`
Expected: 15 passed

- [ ] **Step 5: Commit**

```bash
git add pipeline/chord_detection.py tests/test_chord_detection.py
git commit -m "feat: add bar-to-bar hysteresis smoothing for ambiguous chord bars"
```

---

### Task 6: Wire it all together in `detect_chords`

**Files:**
- Modify: `pipeline/chord_detection.py`

- [ ] **Step 1: Update the module docstring to describe the new approach and limitations**

Replace the module docstring (the very top of the file, before `from __future__ import annotations`) with:
```python
"""Step 4: chord detection via beat-synchronous chroma + template matching,
constrained by the separated bass line and the detected song key, then
smoothed across bars.

We beat-track the harmonic mix, group beats into bars (assuming a constant
4/4 meter -- see limitation below), average the chromagram within each bar,
and match that averaged chroma vector against a bank of chord templates
(major, minor, dominant 7, major 7, minor 7 for all 12 roots) using cosine
similarity. This is the same family of technique as the classic
Fujishima/chroma-template chord recognizers; it is not a learned model.

Two additional signals refine this per bar:
- If the separated bass stem clearly sustains one note for that bar (see
  `_bass_root_pitch_class`), the chord root is forced to that note and only
  that root's 5 templates are searched.
- Otherwise, templates whose root is diatonic to the detected song key get a
  small score bonus (see `_diatonic_roots`/`DIATONIC_BONUS`) -- a soft nudge
  for ambiguous bars, not a hard filter.

After all bars are scored, `_smooth_labels` applies bar-to-bar hysteresis:
an ambiguous bar (bass didn't force its root) whose winning label differs
from its predecessor, but only narrowly beats the predecessor's label on
this bar's own chroma, is pulled back to match its predecessor -- this
corrects incoherent bar-to-bar flip-flopping. Bars with a bass-forced root
are never altered by smoothing.

Known limitations:
- Only 5 chord qualities x 12 roots (60 templates) are covered. sus2/sus4,
  add9, 6th chords, altered dominants, and inversions are NOT modeled and
  will be misclassified as the closest template (usually plain maj/min).
- Meter is assumed to be constant 4/4 (bars = groups of 4 tracked beats).
  Tempo/time-signature changes, pickup bars, or inaccurate beat tracking
  will shift bar boundaries and misalign chords with the tab.
- One chord label per bar is a simplification; genuine chord changes within
  a bar (e.g. two chords per bar) are collapsed into a single "best fit".
- Bass-root forcing assumes the bass plays the chord's root. A bass line
  doubling a non-root chord tone, or sustaining a stable pedal tone that
  isn't the root, will force an incorrect root (rare, but not detected).
- The diatonic bonus is a soft nudge; a wrongly-detected song key (a
  separate, existing limitation of key_detection.py) biases ambiguous-bar
  disambiguation in the wrong direction. Bars with a forced root or a clear
  chroma winner are unaffected.
- Hysteresis only fixes oscillation between close-scoring candidates; a bar
  that is confidently but wrongly detected (e.g. from bad Demucs separation
  bleed) is not corrected by smoothing.
"""
```

- [ ] **Step 2: Replace `detect_chords` entirely**

```python
def detect_chords(y: np.ndarray, sr: int, bass_y: Optional[np.ndarray] = None,
                   bass_sr: Optional[int] = None,
                   key_estimate: Optional[KeyEstimate] = None) -> tuple[List[ChordSegment], float]:
    tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr, units="frames")
    beat_times = librosa.frames_to_time(beat_frames, sr=sr)

    if len(beat_times) < BEATS_PER_BAR:
        duration = librosa.get_duration(y=y, sr=sr)
        beat_times = np.linspace(0, duration, num=max(2, int(duration)))

    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
    chroma_times = librosa.frames_to_time(np.arange(chroma.shape[1]), sr=sr)

    bass_chroma = None
    bass_chroma_times = None
    if bass_y is not None:
        bass_chroma = librosa.feature.chroma_cqt(y=bass_y, sr=bass_sr)
        bass_chroma_times = librosa.frames_to_time(np.arange(bass_chroma.shape[1]), sr=bass_sr)

    diatonic_roots = _diatonic_roots(key_estimate) if key_estimate is not None else None

    bar_starts = beat_times[::BEATS_PER_BAR]
    duration = librosa.get_duration(y=y, sr=sr)
    bar_bounds = list(bar_starts) + [duration]

    bar_results: List[BarResult] = []
    bar_indices: List[int] = []
    for i in range(len(bar_bounds) - 1):
        start, end = bar_bounds[i], bar_bounds[i + 1]
        if end <= start:
            continue
        mask = (chroma_times >= start) & (chroma_times < end)
        if not np.any(mask):
            continue
        bar_chroma = chroma[:, mask].mean(axis=1)

        forced_root = None
        if bass_chroma is not None:
            bass_mask = (bass_chroma_times >= start) & (bass_chroma_times < end)
            if np.any(bass_mask):
                bar_bass_chroma = bass_chroma[:, bass_mask].mean(axis=1)
                forced_root = _bass_root_pitch_class(bar_bass_chroma)

        if forced_root is not None:
            label, score = _best_chord(bar_chroma, forced_root=forced_root)
        else:
            label, score = _best_chord(bar_chroma, diatonic_roots=diatonic_roots)

        bar_results.append(BarResult(label=label, score=score,
                                      root_forced=forced_root is not None,
                                      chroma=bar_chroma))
        bar_indices.append(i)

    smoothed_labels = _smooth_labels(bar_results)

    segments: List[ChordSegment] = []
    for idx, label in zip(bar_indices, smoothed_labels):
        start, end = bar_bounds[idx], bar_bounds[idx + 1]
        segments.append(ChordSegment(bar_index=idx, start=start, end=end, label=label))

    return segments, float(np.asarray(tempo).reshape(-1)[0])
```

- [ ] **Step 3: Run the full test suite**

Run: `./.venv/bin/python3 -m pytest -v`
Expected: all tests pass (15 in `tests/test_chord_detection.py` from Tasks 2-5, plus all pre-existing tests from the tuning-detection feature — 34 total). `detect_chords` itself has no dedicated unit test (like `separation.separate`/`transcription.transcribe`, it needs real or real-ish audio arrays to exercise meaningfully — verified instead via the optional Task 8 smoke test).

- [ ] **Step 4: Commit**

```bash
git add pipeline/chord_detection.py
git commit -m "feat: wire bass root, diatonic bonus, and hysteresis into detect_chords"
```

---

### Task 7: Wire it into `main.py`

**Files:**
- Modify: `main.py`

- [ ] **Step 1: Update the separation call site**

Change:
```python
        print("[1/7] Separating sources with Demucs (htdemucs_6s)...")
        harmonic_path = separation.separate(audio_path, work_dir, device=args.device)
```
to:
```python
        print("[1/7] Separating sources with Demucs (htdemucs_6s)...")
        harmonic_path, bass_stem_path = separation.separate(audio_path, work_dir, device=args.device)
```

- [ ] **Step 2: Load the bass audio alongside the harmonic mix, and update the chord-detection call**

Change:
```python
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
```
to:
```python
        print("[4/7] Loading harmonic mix for key/chord analysis...")
        y, sr = librosa.load(harmonic_path, sr=None, mono=True)
        bass_y, bass_sr = librosa.load(bass_stem_path, sr=None, mono=True)

        print("[5/7] Detecting key (chroma + Krumhansl-Schmuckler)...")
        key_estimate = key_detection.detect_key(y, sr)
        print(f"       -> {key_estimate} (correlation={key_estimate.correlation:.2f})")

        print("[6/7] Detecting chords (bass-root + diatonic-key aware, hysteresis-smoothed)...")
        chords, tempo = chord_detection.detect_chords(y, sr, bass_y, bass_sr, key_estimate)
        print(f"       -> {len(chords)} bars, tempo ~{tempo:.1f} BPM")
```

(This removes the second, redundant `librosa.beat.beat_track` call entirely — `detect_chords` is now the single source of truth for tempo. Do NOT touch the `bass_path` variable that already exists further down inside the `if args.voices == 2:` block — that's the *tab output path* for the bass-register split, an unrelated variable with a similar name; this task's new `bass_stem_path` variable is intentionally named differently to avoid colliding with it.)

- [ ] **Step 3: Run the full test suite**

Run: `./.venv/bin/python3 -m pytest -v`
Expected: all 34 tests still pass (this task only touches `main.py`; `tests/test_main_args.py` only exercises `parse_args()`, which is untouched, so nothing here should regress).

- [ ] **Step 4: Verify `main.py` still parses and the CLI still runs `--help` cleanly**

Run: `./.venv/bin/python3 -c "import ast; ast.parse(open('main.py').read())"`
Expected: no output (valid syntax).

Run: `./.venv/bin/python3 main.py --help`
Expected: same help output as before (no CLI-facing change in this task; the change is internal to `main()`'s body).

- [ ] **Step 5: Commit**

```bash
git add main.py
git commit -m "feat: thread bass stem and detected key into chord detection, drop redundant tempo call"
```

---

### Task 8 (optional manual smoke test): Full pipeline run on real audio

Not part of the automated test suite — re-runs the full, slow (Demucs + basic-pitch) pipeline to confirm the wiring works end-to-end and to subjectively judge whether chord detection actually improved. Skip if time-constrained; Tasks 1-7's automated tests already cover the new logic in isolation.

- [ ] **Step 1: Re-run the pipeline on a song already used with this project**

Run (adjust the input path to any available song):
```bash
cd "/Users/joao.silva/Library/CloudStorage/GoogleDrive-davisthe8th@gmail.com/My Drive/GARAGEBAND/VALLETOFNOONE/guitar_tab_pipeline"
./.venv/bin/python3 main.py "<path/to/a/song>" --tuning "Standard EADGBE" --output /tmp/chord_smoke_test_tab.txt
```
Expected: completes through all 7 steps, printing a bar count and tempo at step 6, and finishing with `Done. Tab written to: /tmp/chord_smoke_test_tab.txt`.

- [ ] **Step 2: Inspect the chord line for musical plausibility**

Run: `head -20 /tmp/chord_smoke_test_tab.txt`
Expected: a chord progression that changes less erratically bar-to-bar than before this feature (no strict automated pass/fail here — this is a subjective spot-check by ear/eye against the source song).
