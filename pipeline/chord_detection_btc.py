"""BTC (Bi-directional Transformer) chord recognition.

Matches Swaram's pipeline exactly:
- Feed BTC the raw full-mix audio (NOT a separated stem — BTC was trained on
  full-mix recordings; separated stems are out-of-distribution and degrade accuracy)
- Median filter (window=5) on per-frame predictions to reduce flickering
- Majority vote per bar for the final label
- Optional bass chroma cross-check to correct the root when the bass strongly
  disagrees with BTC's predicted root

Reference: https://huggingface.co/spaces/vineethwilson/swaram-chord-service
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path
from typing import List, Optional

import librosa
import numpy as np
import torch
import torch.nn.functional as F
from scipy.ndimage import median_filter

# ── BTC on sys.path ─────────────────────────────────────────────────────────
_BTC_DIR = Path(__file__).parent / "btc"
if str(_BTC_DIR) not in sys.path:
    sys.path.insert(0, str(_BTC_DIR))

from btc_model import BTC_model  # noqa: E402
from utils.hparams import HParams  # noqa: E402
from utils.mir_eval_modules import audio_file_to_features, idx2voca_chord  # noqa: E402

from .chord_detection import ChordSegment  # noqa: E402

# ── Paths ────────────────────────────────────────────────────────────────────
_MODEL_PATH = _BTC_DIR / "test" / "btc_model_large_voca.pt"
_CONFIG_PATH = _BTC_DIR / "run_config.yaml"

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

_QUALITY_MAP = {
    "min": "m",
    "maj": "",
    "dim": "dim",
    "aug": "aug",
    "min6": "m6",
    "maj6": "6",
    "min7": "m7",
    "minmaj7": "mmaj7",
    "maj7": "maj7",
    "7": "7",
    "dim7": "dim7",
    "hdim7": "m7b5",
    "sus2": "sus2",
    "sus4": "sus4",
}

BASS_CLARITY_THRESHOLD = 0.38
MEDIAN_FILTER_SIZE = 5    # frames — same as Swaram
VITERBI_SELF_LOOP = 0.88  # lowered from 0.95 → more chord variety, less over-smoothing
MIN_CHORD_DURATION = 0.2  # seconds — dropped from 0.3 to catch quick colour changes

# Chroma-based extension detection threshold:
# extension tone must be this fraction of the max chroma bin to be promoted.
# Use guitar stem chroma (passed in) — cleaner than full mix; no bass/drum bleed.
EXTENSION_THRESHOLD = 0.32


def _btc_to_notara(btc_label: str) -> str:
    if btc_label in ("N", "X"):
        return "N.C."
    if ":" not in btc_label:
        return btc_label  # plain root = major
    root, quality = btc_label.split(":", 1)
    return root + _QUALITY_MAP.get(quality, quality)


# ── Lazy singleton ───────────────────────────────────────────────────────────
_model: Optional[BTC_model] = None
_mean = None
_std = None
_idx_to_chord: Optional[dict] = None
_config = None


def _load_model() -> None:
    global _model, _mean, _std, _idx_to_chord, _config
    if _model is not None:
        return

    cfg = HParams.load(str(_CONFIG_PATH))
    cfg.feature["large_voca"] = True
    cfg.model["num_chords"] = 170

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    m = BTC_model(config=cfg.model).to(device)

    checkpoint = torch.load(str(_MODEL_PATH), map_location=device, weights_only=False)
    _mean = checkpoint["mean"]
    _std = checkpoint["std"]
    m.load_state_dict(checkpoint["model"])
    m.eval()

    _model = m
    _idx_to_chord = idx2voca_chord()
    _config = cfg


def _viterbi_smooth(log_probs: np.ndarray, self_loop: float = VITERBI_SELF_LOOP) -> List[int]:
    """Viterbi HMM smoothing on per-frame log-probability matrix.

    Transition model: P(stay) = self_loop, P(switch to any other) uniform.
    Uses an O(T*N) trick — since all off-diagonal transitions share one value,
    only the global max and second max of the previous step are needed.

    Args:
        log_probs: (T, N) log probabilities from BTC (log-softmax output).
        self_loop: probability of staying on the current chord each frame.

    Returns:
        List of T chord indices after Viterbi decoding.
    """
    T, N = log_probs.shape
    log_self  = np.log(self_loop)
    log_other = np.log((1.0 - self_loop) / max(N - 1, 1))

    viterbi = log_probs[0].copy()
    backptr  = np.zeros((T, N), dtype=np.int32)

    for t in range(1, T):
        # Find the best and second-best previous state efficiently
        best1_idx = int(np.argmax(viterbi))
        best1_val = viterbi[best1_idx]
        # Mask out best1 to find second best
        viterbi_copy = viterbi.copy()
        viterbi_copy[best1_idx] = -np.inf
        best2_idx = int(np.argmax(viterbi_copy))
        best2_val = viterbi_copy[best2_idx]

        for j in range(N):
            # Self-loop score
            stay_score = viterbi[j] + log_self
            # Best incoming transition from a different state
            if j == best1_idx:
                switch_score = best2_val + log_other
                switch_from  = best2_idx
            else:
                switch_score = best1_val + log_other
                switch_from  = best1_idx

            if stay_score >= switch_score:
                viterbi[j] = log_probs[t, j] + stay_score
                backptr[t, j] = j
            else:
                viterbi[j] = log_probs[t, j] + switch_score
                backptr[t, j] = switch_from

    # Traceback
    path = [int(np.argmax(viterbi))]
    for t in range(T - 1, 0, -1):
        path.append(int(backptr[t, path[-1]]))
    path.reverse()
    return path


def _group_frame_events(
    frame_preds: List[int],
    feature_per_second: float,
    idx_to_chord: dict,
    song_duration: float,
    min_duration: float = MIN_CHORD_DURATION,
) -> List[ChordSegment]:
    """Convert Viterbi frame predictions into chord-change events.

    Groups consecutive frames with the same prediction into one event.
    Drops events shorter than `min_duration` seconds (same as Swaram) and
    merges them into the adjacent event.  Returns ChordSegments with exact
    onset/offset times — not bar-aligned.
    """
    if not frame_preds:
        return []

    events: List[ChordSegment] = []
    run_start = 0
    current = frame_preds[0]

    def _push(start_f: int, end_f: int, chord_idx: int) -> None:
        label = _btc_to_notara(idx_to_chord[chord_idx])
        start_t = start_f * feature_per_second
        end_t   = min(end_f * feature_per_second, song_duration)
        events.append(ChordSegment(
            bar_index=len(events),
            start=start_t,
            end=end_t,
            label=label,
        ))

    for f in range(1, len(frame_preds)):
        if frame_preds[f] != current:
            _push(run_start, f, current)
            run_start = f
            current = frame_preds[f]
    _push(run_start, len(frame_preds), current)

    # Merge events shorter than min_duration into the previous event
    merged: List[ChordSegment] = []
    for ev in events:
        if ev.label == "N.C.":
            merged.append(ev)
            continue
        if (ev.end - ev.start) < min_duration and merged:
            # Absorb into previous: extend its end, keep its label
            prev = merged[-1]
            merged[-1] = ChordSegment(
                bar_index=prev.bar_index,
                start=prev.start,
                end=ev.end,
                label=prev.label,
            )
        else:
            merged.append(ev)

    # Re-index
    return [ChordSegment(i, e.start, e.end, e.label) for i, e in enumerate(merged)]


def _bass_forced_root(bass_chroma_vec: np.ndarray) -> Optional[int]:
    total = float(np.sum(bass_chroma_vec))
    if total <= 0:
        return None
    if float(np.max(bass_chroma_vec)) / total < BASS_CLARITY_THRESHOLD:
        return None
    return int(np.argmax(bass_chroma_vec))


def _apply_bass_crosscheck(btc_label: str, bar_bass_chroma: Optional[np.ndarray]) -> str:
    if bar_bass_chroma is None or btc_label == "N.C.":
        return btc_label
    forced = _bass_forced_root(bar_bass_chroma)
    if forced is None:
        return btc_label
    for length in (2, 1):
        root_candidate = btc_label[:length]
        if root_candidate in NOTE_NAMES:
            if NOTE_NAMES.index(root_candidate) == forced:
                return btc_label
            return NOTE_NAMES[forced] + btc_label[length:]
    return btc_label


def _extend_chord_label(label: str, chroma: np.ndarray) -> str:
    """Upgrade a BTC chord label with extensions detected from the chroma vector.

    BTC's 170-chord vocab covers triads + 7ths + sus but not 9ths, add9, or
    altered tones.  This function adds those on top of BTC's root+quality guess.

    Semitone intervals relative to root:
      m7=10, M7=11, M9=2, M6=9, P4=5, A4/#11=6, b9=1, #9=3
    """
    if label == "N.C." or chroma is None:
        return label

    # Parse root
    root_name = None
    quality = label
    for length in (2, 1):
        if label[:length] in NOTE_NAMES:
            root_name = label[:length]
            quality = label[length:]
            break
    if root_name is None:
        return label

    root_idx = NOTE_NAMES.index(root_name)
    c = np.roll(chroma, -root_idx).astype(float)
    peak = c.max()
    if peak < 1e-8:
        return label
    c /= peak  # normalize so max = 1.0

    ninth   = c[2]   # M9  (also M2)
    flat9   = c[1]   # b9
    sharp9  = c[3]   # #9  (also m3 in alt dominant context)
    fourth  = c[5]   # P4 / sus4 tone
    sharp11 = c[6]   # #11 / b5 (tritone)
    sixth   = c[9]   # M6
    flat7   = c[10]  # m7 (dominant)
    major7  = c[11]  # M7

    thr = EXTENSION_THRESHOLD

    # ── Major triad: check for 7ths, 9ths, sus, add ──────────────────────────
    if quality == "":
        # Dominant alterations (flat7 present)
        if flat7 >= thr:
            if flat9 >= thr:
                return root_name + "7b9"
            if sharp9 >= thr:
                return root_name + "7#9"
            if sharp11 >= thr:
                return root_name + "7#11"
            if ninth >= thr:
                return root_name + "9"
            return root_name + "7"
        if major7 >= thr:
            if ninth >= thr:
                return root_name + "maj9"
            return root_name + "maj7"
        if sixth >= thr and ninth >= thr:
            return root_name + "6/9"
        if sixth >= thr:
            return root_name + "6"
        if ninth >= thr:
            return root_name + "add9"

    # ── Minor triad ───────────────────────────────────────────────────────────
    elif quality == "m":
        if flat7 >= thr:
            if ninth >= thr:
                return root_name + "m9"
            if sixth >= thr:
                return root_name + "m7"   # m13 simplified
            return root_name + "m7"
        if major7 >= thr:
            return root_name + "mmaj7"
        if sixth >= thr:
            return root_name + "m6"
        if ninth >= thr:
            return root_name + "madd9"

    # ── Dominant 7 → 9, 11, 13 ───────────────────────────────────────────────
    elif quality == "7":
        if ninth >= thr:
            return root_name + "9"
        if flat9 >= thr:
            return root_name + "7b9"
        if sharp9 >= thr:
            return root_name + "7#9"
        if sharp11 >= thr:
            return root_name + "7#11"
        if sixth >= thr:
            return root_name + "13"

    # ── Major 7 → maj9 ───────────────────────────────────────────────────────
    elif quality == "maj7":
        if ninth >= thr:
            return root_name + "maj9"
        if sharp11 >= thr:
            return root_name + "maj7#11"

    # ── Minor 7 → m9, m11 ────────────────────────────────────────────────────
    elif quality == "m7":
        if ninth >= thr:
            return root_name + "m9"
        if fourth >= thr:
            return root_name + "m11"

    return label


def detect_chords_btc(
    full_mix_path: Path,
    bar_segments: List[ChordSegment],
    bass_chroma: Optional[np.ndarray] = None,
    bass_chroma_times: Optional[np.ndarray] = None,
    guitar_chroma: Optional[np.ndarray] = None,
    guitar_chroma_times: Optional[np.ndarray] = None,
) -> tuple[List[ChordSegment], List[ChordSegment]]:
    """Run BTC chord recognition and return two chord lists.

    Returns:
        (bar_segments_labeled, chord_events) where:
        - bar_segments_labeled: bar-aligned segments with BTC labels (for tab notation)
        - chord_events: frame-level chord-change events (for frontend playback display)
          These are not bar-aligned — they fire at the actual moment chords change,
          giving the same precision as Swaram.

    Args:
        full_mix_path: original audio file (full mix, not a separated stem).
        bar_segments: bar timing from beat tracker (.label is replaced).
        bass_chroma / bass_chroma_times: bass chroma for root correction.
        guitar_chroma / guitar_chroma_times: guitar stem chroma for extension detection.
            If not provided, falls back to harmonic HPSS of the full mix (less accurate).
    """
    _load_model()

    # ── Chroma for extension detection ───────────────────────────────────────
    # Prefer guitar stem (cleaner, no bass/drum bleed); fall back to full mix HPSS.
    if guitar_chroma is not None and guitar_chroma_times is not None:
        ext_chroma = guitar_chroma
        ext_chroma_times = guitar_chroma_times
    else:
        _y, _sr = librosa.load(str(full_mix_path), sr=22050, mono=True)
        _harm, _ = librosa.effects.hpss(_y)
        ext_chroma = librosa.feature.chroma_cens(y=_harm, sr=_sr)
        ext_chroma_times = librosa.frames_to_time(np.arange(ext_chroma.shape[1]), sr=_sr)

    # ── Feature extraction (full mix → BTC's own CQT pipeline) ──────────────
    feature, feature_per_second, song_length = audio_file_to_features(str(full_mix_path), _config)

    feature = feature.T  # (n_frames, n_bins)
    feature = (feature - _mean) / _std

    n_timestep = _config.model["timestep"]
    num_pad = n_timestep - (feature.shape[0] % n_timestep)
    feature = np.pad(feature, ((0, num_pad), (0, 0)), mode="constant", constant_values=0)
    num_instance = feature.shape[0] // n_timestep

    # ── Inference — per-frame log-probabilities for Viterbi ──────────────────
    device = next(_model.parameters()).device
    all_log_probs: List[np.ndarray] = []

    with torch.no_grad():
        feat_t = torch.tensor(feature, dtype=torch.float32).unsqueeze(0).to(device)
        for t in range(num_instance):
            attn_out, _ = _model.self_attn_layers(feat_t[:, n_timestep * t: n_timestep * (t + 1), :])
            logits    = _model.output_layer.output_projection(attn_out)  # (1, n_timestep, N)
            log_probs = F.log_softmax(logits, dim=-1).squeeze(0)         # (n_timestep, N)
            all_log_probs.append(log_probs.cpu().numpy())

    # ── Viterbi HMM smoothing ─────────────────────────────────────────────────
    log_probs_matrix = np.concatenate(all_log_probs, axis=0)  # (T_total, N)
    frame_preds      = _viterbi_smooth(log_probs_matrix)
    n_frames_total   = len(frame_preds)

    # ── 1. Frame-level chord events (for frontend — Swaram-style precision) ──
    chord_events_raw = _group_frame_events(
        frame_preds, feature_per_second, _idx_to_chord, song_length
    )
    # Apply chroma extension upgrade to each frame event
    chord_events: List[ChordSegment] = []
    for ev in chord_events_raw:
        mask = (ext_chroma_times >= ev.start) & (ext_chroma_times < ev.end)
        label = ev.label
        if np.any(mask):
            label = _extend_chord_label(ev.label, ext_chroma[:, mask].mean(axis=1))
        chord_events.append(ChordSegment(ev.bar_index, ev.start, ev.end, label))

    # ── 2. Bar-aligned segments (for tab notation — majority vote per bar) ───
    new_segments: List[ChordSegment] = []
    for seg in bar_segments:
        start_f = int(seg.start / feature_per_second)
        end_f   = min(int(seg.end / feature_per_second), n_frames_total)

        if start_f >= end_f:
            notara_label = "N.C."
        else:
            bar_frames = frame_preds[start_f:end_f]
            best_idx   = Counter(bar_frames).most_common(1)[0][0]
            notara_label = _btc_to_notara(_idx_to_chord[best_idx])

        # Bass root cross-check on bar-aligned label
        if bass_chroma is not None and bass_chroma_times is not None:
            bass_mask = (bass_chroma_times >= seg.start) & (bass_chroma_times < seg.end)
            if np.any(bass_mask):
                notara_label = _apply_bass_crosscheck(
                    notara_label, bass_chroma[:, bass_mask].mean(axis=1)
                )

        # Chroma extension upgrade (add9, 9, m9, 7b9, etc.)
        chroma_mask = (ext_chroma_times >= seg.start) & (ext_chroma_times < seg.end)
        if np.any(chroma_mask):
            bar_chroma = ext_chroma[:, chroma_mask].mean(axis=1)
            notara_label = _extend_chord_label(notara_label, bar_chroma)

        new_segments.append(ChordSegment(
            bar_index=seg.bar_index,
            start=seg.start,
            end=seg.end,
            label=notara_label,
        ))

    return new_segments, chord_events
