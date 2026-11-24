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
corrects incoherent bar-to-bar flip-flopping. Bars with a bass-forced root,
and genuinely silent ("N.C.") bars, are never altered by smoothing.

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
  bleed) is not corrected by smoothing. Over a long run of consecutive
  ambiguous bars each only narrowly beating the previous one, hysteresis can
  also "drift" the whole run toward an early bar's read rather than any
  individual bar's own best evidence -- a known trade-off of any simple
  bar-to-bar debounce scheme.
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

BEATS_PER_BAR = 4  # assumes 4/4 time (see module docstring)

# Fraction of a bar's bass chroma energy that must be concentrated in a single
# pitch class for that pitch class to be treated as a forced chord root.
# Heuristic/tunable, like CHORD_TOLERANCE elsewhere in this pipeline -- not
# derived from any formal model.
BASS_CLARITY_THRESHOLD = 0.38

# Kept very small — a large bonus was biasing chord detection toward "expected"
# diatonic chords even when the audio clearly said something else.
DIATONIC_BONUS = 0.005

# Maximum score gap (cosine-similarity scale) for hysteresis smoothing to
# keep the previous bar's label instead of switching to the current bar's
# own (different) winning label.
HYSTERESIS_MARGIN = 0.04

# Minimum cosine-similarity score for each half-bar to be considered reliable
# enough to justify showing a split chord (e.g. "Em7 / D6") in the rehearsal sheet.
HALF_BAR_SPLIT_MIN_SCORE = 0.40

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
    first bar has no predecessor, so it's never altered either. Genuinely
    silent bars (label "N.C.") are never altered in either direction.
    """
    if not bar_results:
        return []
    labels = [bar_results[0].label]
    for i in range(1, len(bar_results)):
        current = bar_results[i]
        previous_label = labels[i - 1]
        if current.root_forced or current.label == previous_label or previous_label == "N.C." or current.label == "N.C.":
            labels.append(current.label)
            continue
        previous_label_score_here = _score_label(current.chroma, previous_label)
        if current.score - previous_label_score_here <= margin:
            labels.append(previous_label)
        else:
            labels.append(current.label)
    return labels


def _notes_to_pc_weights(notes: list, start: float, end: float) -> np.ndarray:
    """Build a 12-bin pitch-class weight vector from notes active in [start, end].

    Each note contributes weight = overlap_duration * velocity, so long sustained
    notes and loud notes both count more — which is what matters for chord identity.
    """
    pc_weights = np.zeros(12)
    for n in notes:
        overlap = min(n.end, end) - max(n.start, start)
        if overlap <= 0:
            continue
        pc_weights[int(n.pitch) % 12] += overlap * float(n.velocity)
    return pc_weights


def detect_chords(y: np.ndarray, sr: int, bass_y: Optional[np.ndarray] = None,
                   bass_sr: Optional[int] = None,
                   key_estimate: Optional[KeyEstimate] = None,
                   notes: Optional[list] = None) -> tuple[List[ChordSegment], float]:
    """Detect chords.

    When `notes` (from basic-pitch transcription of the guitar stem) are provided,
    chord quality is derived from the actual detected pitches — far more accurate
    than chroma template matching. Bass chroma is still used for root forcing.
    When notes are absent, falls back to chroma template matching.
    """
    tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr, units="frames")
    beat_times = librosa.frames_to_time(beat_frames, sr=sr)

    if len(beat_times) < BEATS_PER_BAR:
        duration = librosa.get_duration(y=y, sr=sr)
        beat_times = np.linspace(0, duration, num=max(2, int(duration)))

    # Chroma is still used for fallback bars (no notes) and for bass root forcing.
    y_harmonic, _ = librosa.effects.hpss(y)
    chroma = librosa.feature.chroma_cens(y=y_harmonic, sr=sr)
    chroma_times = librosa.frames_to_time(np.arange(chroma.shape[1]), sr=sr)

    bass_chroma = None
    bass_chroma_times = None
    if bass_y is not None:
        bass_harmonic, _ = librosa.effects.hpss(bass_y)
        bass_chroma = librosa.feature.chroma_cens(y=bass_harmonic, sr=bass_sr)
        bass_chroma_times = librosa.frames_to_time(np.arange(bass_chroma.shape[1]), sr=bass_sr)

    diatonic_roots = _diatonic_roots(key_estimate) if key_estimate is not None else None

    bar_starts = beat_times[::BEATS_PER_BAR]
    duration = librosa.get_duration(y=y, sr=sr)
    bar_bounds = list(bar_starts) + [duration]

    bar_results: List[BarResult] = []
    bar_indices: List[int] = []
    bar_beat_splits: List[Optional[str]] = []  # parallel to bar_results; None = no intra-bar split
    for i in range(len(bar_bounds) - 1):
        start, end = bar_bounds[i], bar_bounds[i + 1]
        if end <= start:
            continue

        # ── Choose chord evidence source ──────────────────────────────────────
        if notes is not None:
            bar_vec = _notes_to_pc_weights(notes, start, end)
            used_notes = bar_vec.sum() > 0
        else:
            used_notes = False

        if not used_notes:
            # Fallback: chroma from audio
            mask = (chroma_times >= start) & (chroma_times < end)
            if not np.any(mask):
                continue
            bar_vec = chroma[:, mask].mean(axis=1)

        # ── Bass root forcing (still from bass chroma) ────────────────────────
        forced_root = None
        if bass_chroma is not None:
            bass_mask = (bass_chroma_times >= start) & (bass_chroma_times < end)
            if np.any(bass_mask):
                bar_bass_chroma = bass_chroma[:, bass_mask].mean(axis=1)
                forced_root = _bass_root_pitch_class(bar_bass_chroma)

        if forced_root is not None:
            label, score = _best_chord(bar_vec, forced_root=forced_root)
        else:
            label, score = _best_chord(bar_vec, diatonic_roots=diatonic_roots)

        # BarResult always receives a clean single-chord label so _smooth_labels
        # can call _score_label on it without crashing. Beat-level splits are
        # computed separately below and applied after smoothing.
        bar_results.append(BarResult(label=label, score=score,
                                      root_forced=forced_root is not None,
                                      chroma=bar_vec))
        bar_indices.append(i)

        # ── Beat-level split (stored separately, applied post-smoothing) ──────
        # Analyse each beat individually; collapse consecutive identical labels.
        # Result is None when the bar is uniform (no split needed).
        split_label: Optional[str] = None
        bar_beat_start = i * BEATS_PER_BAR
        bar_beat_times = beat_times[bar_beat_start: bar_beat_start + BEATS_PER_BAR]
        if len(bar_beat_times) == BEATS_PER_BAR:
            beat_bounds = list(bar_beat_times) + [end]
            beat_labels: List[str] = []
            for b in range(BEATS_PER_BAR):
                bt0, bt1 = beat_bounds[b], beat_bounds[b + 1]
                # Evidence vector for this beat
                bv: Optional[np.ndarray] = None
                if notes is not None:
                    bv = _notes_to_pc_weights(notes, bt0, bt1)
                    if bv.sum() == 0:
                        bv = None
                if bv is None:
                    bmask = (chroma_times >= bt0) & (chroma_times < bt1)
                    bv = chroma[:, bmask].mean(axis=1) if np.any(bmask) else None
                if bv is None:
                    beat_labels.append(label)
                    continue
                # Bass root for this beat
                br: Optional[int] = None
                if bass_chroma is not None:
                    bm = (bass_chroma_times >= bt0) & (bass_chroma_times < bt1)
                    if np.any(bm):
                        br = _bass_root_pitch_class(bass_chroma[:, bm].mean(axis=1))
                bl, bs = _best_chord(bv, forced_root=br,
                                     diatonic_roots=diatonic_roots if br is None else None)
                beat_labels.append(bl if bs >= HALF_BAR_SPLIT_MIN_SCORE else label)

            # Collapse consecutive identical beat labels
            collapsed: List[str] = []
            for bl in beat_labels:
                if not collapsed or collapsed[-1] != bl:
                    collapsed.append(bl)
            if len(collapsed) > 1:
                split_label = " / ".join(collapsed)

        bar_beat_splits.append(split_label)

    smoothed_labels = _smooth_labels(bar_results)

    segments: List[ChordSegment] = []
    for j, (idx, smooth_label) in enumerate(zip(bar_indices, smoothed_labels)):
        start, end = bar_bounds[idx], bar_bounds[idx + 1]
        # Apply beat split override when available
        final_label = bar_beat_splits[j] if bar_beat_splits[j] is not None else smooth_label
        segments.append(ChordSegment(bar_index=idx, start=start, end=end, label=final_label))

    return segments, float(np.asarray(tempo).reshape(-1)[0])
