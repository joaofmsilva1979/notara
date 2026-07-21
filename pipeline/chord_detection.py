"""Step 4: chord detection via beat-synchronous chroma + template matching.

We beat-track the harmonic mix, group beats into bars (assuming a constant
4/4 meter -- see limitation below), average the chromagram within each bar,
and match that averaged chroma vector against a bank of chord templates
(major, minor, dominant 7, major 7, minor 7 for all 12 roots) using cosine
similarity. This is the same family of technique as the classic
Fujishima/chroma-template chord recognizers; it is not a learned model.

Known limitations:
- Only 5 chord qualities x 12 roots (60 templates) are covered. sus2/sus4,
  add9, 6th chords, altered dominants, and inversions are NOT modeled and
  will be misclassified as the closest template (usually plain maj/min).
- Meter is assumed to be constant 4/4 (bars = groups of 4 tracked beats).
  Tempo/time-signature changes, pickup bars, or inaccurate beat tracking
  will shift bar boundaries and misalign chords with the tab.
- One chord label per bar is a simplification; genuine chord changes within
  a bar (e.g. two chords per bar) are collapsed into a single "best fit".
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import librosa
import numpy as np

from .key_detection import KeyEstimate

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# (suffix, semitone intervals from root)
CHORD_TYPES = [
    ("", [0, 4, 7]),        # major
    ("m", [0, 3, 7]),       # minor
    ("7", [0, 4, 7, 10]),   # dominant 7th
    ("maj7", [0, 4, 7, 11]),  # major 7th
    ("m7", [0, 3, 7, 10]),  # minor 7th
]

BEATS_PER_BAR = 4  # assumes 4/4 time (see module docstring)

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

MAJOR_SCALE_INTERVALS = [0, 2, 4, 5, 7, 9, 11]
MINOR_SCALE_INTERVALS = [0, 2, 3, 5, 7, 8, 10]  # natural minor


@dataclass
class ChordSegment:
    bar_index: int
    start: float
    end: float
    label: str


@dataclass
class BarResult:
    label: str
    score: float
    root_forced: bool
    chroma: np.ndarray


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


def _score_label(chroma_vec: np.ndarray, label: str) -> float:
    """Cosine similarity between `chroma_vec` and the named chord template."""
    # Validate label exists first, before checking norm
    template = None
    for _root, template_label, tmpl in _TEMPLATES:
        if template_label == label:
            template = tmpl
            break
    if template is None:
        raise ValueError(f"Unknown chord label: {label!r}")

    norm = np.linalg.norm(chroma_vec)
    if norm == 0:
        return 0.0
    normalized = chroma_vec / norm
    return float(np.dot(normalized, template))


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


def _diatonic_roots(key_estimate: KeyEstimate) -> set[int]:
    """The 7 scale-degree root pitch classes for `key_estimate`'s tonic/mode."""
    tonic_index = NOTE_NAMES.index(key_estimate.tonic)
    intervals = MAJOR_SCALE_INTERVALS if key_estimate.mode == "major" else MINOR_SCALE_INTERVALS
    return {(tonic_index + interval) % 12 for interval in intervals}


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


def detect_chords(y: np.ndarray, sr: int) -> List[ChordSegment]:
    tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr, units="frames")
    beat_times = librosa.frames_to_time(beat_frames, sr=sr)

    if len(beat_times) < BEATS_PER_BAR:
        duration = librosa.get_duration(y=y, sr=sr)
        beat_times = np.linspace(0, duration, num=max(2, int(duration)))

    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
    chroma_times = librosa.frames_to_time(np.arange(chroma.shape[1]), sr=sr)

    bar_starts = beat_times[::BEATS_PER_BAR]
    duration = librosa.get_duration(y=y, sr=sr)
    bar_bounds = list(bar_starts) + [duration]

    segments: List[ChordSegment] = []
    for i in range(len(bar_bounds) - 1):
        start, end = bar_bounds[i], bar_bounds[i + 1]
        if end <= start:
            continue
        mask = (chroma_times >= start) & (chroma_times < end)
        if not np.any(mask):
            continue
        bar_chroma = chroma[:, mask].mean(axis=1)
        label = _best_chord(bar_chroma)
        segments.append(ChordSegment(bar_index=i, start=start, end=end, label=label))

    return segments
