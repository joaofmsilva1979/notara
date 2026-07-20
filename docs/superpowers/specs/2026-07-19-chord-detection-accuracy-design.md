# Chord Detection Accuracy — Design Spec

## Context

- Existing pipeline (`guitar_tab_pipeline`): `pipeline/chord_detection.py` (Step 4) currently computes beat-synchronous chroma from the harmonic mix (guitar+other Demucs stems only), and independently picks the best-matching chord template (argmax cosine similarity over 60 templates: 5 qualities × 12 roots) per bar. There is no use of the bass line, the detected song key, or any awareness of neighboring bars.
- Demucs (`htdemucs_6s`) already separates a dedicated `bass.wav` stem, but `pipeline/separation.py`'s `_combine_stems` only keeps `HARMONIC_STEMS = ("guitar", "other")` — the bass stem is silently discarded today.
- Real-audio testing (on `too-bad-old.mp3`, see prior conversation) showed the pipeline's automatic note-by-note tab generation is not musically credible — confirming a known, previously-flagged limitation. Decision made earlier: demote full automatic tab generation to a secondary/manual-correction feature, and instead invest in making chord detection as reliable as possible, since that's closer to CAPO's actual core value and a much more tractable problem.

## Goal

Improve `chord_detection.py`'s accuracy using signals already available elsewhere in the pipeline but not currently used:

1. **Bass line** (Demucs's already-produced but discarded `bass.wav` stem) — a strong constraint on the chord's root when the bass is clearly playing a single sustained note.
2. **Adjacent-bar hysteresis** (temporal smoothing) — corrects incoherent bar-to-bar chord flip-flopping for ambiguous bars.

Plus two smaller correctness fixes surfaced during design:

3. **Detected song key** as a soft diatonic tie-breaker for ambiguous bars.
4. **Single source of truth for tempo** — currently computed twice (once inside chord detection's own beat-tracking, once again in `main.py` for the printed BPM), which is redundant and can produce a tempo that doesn't match what was actually used to segment bars.

**Explicitly out of scope** for this chantier: expanding the chord vocabulary beyond the current 5 qualities (maj/min/7/maj7/m7) × 12 roots (a separate, later chantier if needed).

## Architecture & Data Flow

### `pipeline/separation.py`

`separate()` currently returns a single `Path` (the combined guitar+other harmonic mix) and discards the bass stem entirely. Change: return `(harmonic_path, bass_path)`, where `bass_path = stem_dir / "bass.wav"` — Demucs already writes this file for `htdemucs_6s`, no extra computation needed. Raise `FileNotFoundError` if it's missing, consistent with the module's existing pattern for a missing `stem_dir`.

### `pipeline/chord_detection.py`

Refactored into small, independently testable pure functions (chroma-vector in, decision out — no audio I/O), so the new logic can be unit-tested with synthetic chroma vectors instead of requiring real audio or Demucs:

- `_bass_root_pitch_class(bass_chroma_vec: np.ndarray, threshold: float = BASS_CLARITY_THRESHOLD) -> Optional[int]`
  Returns the dominant pitch class (0–11) if the bass chroma vector is concentrated enough on one bin (see Thresholds below), else `None`.
- `_score_label(chroma_vec: np.ndarray, label: str) -> float`
  Extracted from the existing `_best_chord` loop body: cosine similarity between a chroma vector and one named template.
- `_diatonic_roots(key_estimate: KeyEstimate) -> set[int]`
  Returns the 7 scale-degree root pitch classes for the detected key/mode (major scale intervals `[0,2,4,5,7,9,11]` or natural-minor `[0,2,3,5,7,8,10]`, rotated to the tonic).
- `_best_chord(chroma_vec: np.ndarray, forced_root: Optional[int] = None, diatonic_roots: Optional[set[int]] = None) -> tuple[str, float]`
  Same cosine-similarity template matching as today, but:
  - if `forced_root` is given, only the 5 templates for that root are considered;
  - else if `diatonic_roots` is given, a small bonus (`DIATONIC_BONUS`) is added to the score of templates whose root is in that set, before picking the argmax — a soft nudge, not a filter (a strongly-evidenced non-diatonic chord can still win).
- `_smooth_labels(bar_results: List[BarResult], margin: float = HYSTERESIS_MARGIN) -> List[str]`
  `BarResult` bundles `(label, score, root_forced: bool)` per bar. Walks bars in order; for each bar where `root_forced` is `False` and its label differs from the previous (already-smoothed) bar's label, re-scores the previous bar's label against this bar's chroma — if that score is within `margin` of this bar's own winning score, keep the previous label instead of switching. Bars with `root_forced = True` are never altered by smoothing (bass evidence takes priority, per earlier decision). The first bar has no predecessor, so hysteresis never applies to it — it always keeps its own `_best_chord` result.

`detect_chords(y: np.ndarray, sr: int, bass_y: Optional[np.ndarray] = None, bass_sr: Optional[int] = None, key_estimate: Optional[KeyEstimate] = None) -> tuple[List[ChordSegment], float]`

Orchestrates the above, per bar:
1. Compute this bar's harmonic chroma (as today) and, if `bass_y` is given, this bar's bass chroma.
2. If the bass chroma yields a clear pitch class (`_bass_root_pitch_class`), call `_best_chord(harmonic_chroma, forced_root=that_pitch_class)`.
3. Else call `_best_chord(harmonic_chroma, diatonic_roots=_diatonic_roots(key_estimate) if key_estimate else None)`.
4. Collect all bars' `BarResult`s, then run `_smooth_labels` once over the whole song.

Returns `(segments, tempo)` — tempo computed once internally (from the same beat-tracking pass already used for bar boundaries) and returned, rather than `main.py` re-deriving it with a second `beat_track` call.

### `main.py`

- `harmonic_path, bass_path = separation.separate(...)` (was a single return value).
- After key detection (Step 5, unchanged) and at Step 6: load the bass audio (`librosa.load(bass_path, sr=None, mono=True)`), then call `chords, tempo = chord_detection.detect_chords(y, sr, bass_y, bass_sr, key_estimate)`.
- Remove the now-redundant second `librosa.beat.beat_track` call; use the `tempo` returned from `detect_chords` for both the printed BPM and `tab_render.write_tab`.

## Thresholds

Heuristic, documented as approximate/tunable — consistent with the rest of the pipeline's existing style (e.g. `CHORD_TOLERANCE`, tuning's `min_confidence`):

- `BASS_CLARITY_THRESHOLD = 0.35` — fraction of a bar's bass chroma energy concentrated in its top bin, for that bin to be treated as a forced root. Below this, the bass is treated as ambiguous (silence, walking bass, chord/double-stop) and the bar falls back to unconstrained matching.
- `DIATONIC_BONUS = 0.03` — additive score bonus (on the `[0,1]` cosine-similarity scale) for templates whose root is diatonic to the detected key, applied only when there is no forced root.
- `HYSTERESIS_MARGIN = 0.05` — maximum score gap (cosine-similarity scale) for hysteresis to keep the previous bar's label instead of switching.

## Known Limitations (to document in the module docstring, matching existing style)

- Bass-root forcing assumes the bass plays the chord's root. Walking bass lines, bass doubling a non-root chord tone (e.g. a 3rd), or bass silence/rests will not trigger the constraint (falls back to unconstrained matching) — but a bass sustaining a stable *non-root* note (rare, e.g. a pedal tone) would force an incorrect root. Accepted trade-off per the earlier decision to treat bass as a strong constraint.
- The diatonic bonus is a soft nudge; a wrongly-detected key (an existing, separate limitation of `key_detection.py`) will bias chord disambiguation in the wrong direction for ambiguous bars specifically — bars with strong bass evidence or clear chroma evidence are unaffected.
- Hysteresis only cleans up bar-to-bar oscillation between close-scoring candidates; a bar whose true chord is confidently but wrongly detected (e.g. from bad Demucs separation bleed) is not fixed by smoothing.
- Chord vocabulary is unchanged (5 qualities × 12 roots) — sus/6th/add9/altered chords remain out of scope for this chantier.

## Testing

New `tests/test_chord_detection.py`, using synthetic chroma vectors (hand-built numpy arrays) — no real audio, no Demucs, no librosa audio loading needed for the unit-level logic:

- `_bass_root_pitch_class`: a clear single-bin vector returns that pitch class; a near-uniform/silent vector returns `None`.
- `_best_chord` with `forced_root`: only searches that root's 5 templates, ignoring a higher-scoring template with a different root.
- `_best_chord` with `diatonic_roots`: a small bonus changes the winner only when scores are close; a clearly-better non-diatonic template still wins despite the bonus.
- `_diatonic_roots`: correct 7-note sets for at least one major and one minor key.
- `_smooth_labels`: an isolated close-scoring bar between two identical neighboring bars gets pulled to match them; a bar with `root_forced=True` is never changed regardless of score gap; a bar with a clearly-dominant score (gap larger than the margin) is not smoothed away; the first bar in the sequence is never altered (no predecessor to compare against).

`detect_chords()` itself stays integration-level (like today — no dedicated unit test), matching the existing precedent for functions that require real or real-ish audio (`separation.py`, `transcription.py` have no unit tests either, for the same reason).

## Out of Scope

- Chord vocabulary expansion (sus/6th/add9/altered chords) — deferred to a separate, later chantier if needed.
- Any change to the automatic note-by-note tab generation itself (already demoted to a secondary/manual-correction feature in an earlier discussion; not part of this chantier).
