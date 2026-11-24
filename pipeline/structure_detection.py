"""Song structure detection — intro / verse / chorus / bridge / outro.

Uses librosa's agglomerative segmentation on beat-synced chroma + MFCC
features, then clusters segments by acoustic similarity to assign labels.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import List

import numpy as np
import librosa


@dataclass
class SongSection:
    label: str       # "A", "B", "C" ...
    type: str        # "intro" | "verse" | "chorus" | "bridge" | "outro"
    start_sec: float
    end_sec: float
    bar_start: int   # inclusive index into bars list
    bar_end: int     # exclusive


SECTION_DISPLAY = {
    "intro":  "INTRO",
    "verse":  "COUPLET",
    "chorus": "REFRAIN",
    "bridge": "PONT",
    "outro":  "OUTRO",
}

_HOP = 512
_TARGET_SR = 22050


def detect_structure(
    y: np.ndarray,
    sr: int,
    bars: list,       # list of dicts: {'start_sec': float, 'end_sec': float}
    n_target: int = 8,
) -> List[SongSection]:
    """
    Detect song sections from audio.

    Parameters
    ----------
    y        : mono audio signal (any sr)
    sr       : sample rate of y
    bars     : bar list with 'start_sec' / 'end_sec' keys
    n_target : target segment count for agglomerative segmentation

    Returns ordered list of SongSection. Empty list on failure.
    """
    if len(bars) < 4:
        return []

    # Resample once to fixed sr for all feature extraction
    if sr != _TARGET_SR:
        y = librosa.resample(y, orig_sr=sr, target_sr=_TARGET_SR)
        sr = _TARGET_SR

    duration = float(len(y)) / sr

    # ── Features ────────────────────────────────────────────────
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=_HOP)
    mfcc   = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=6, hop_length=_HOP)
    rms    = librosa.feature.rms(y=y, hop_length=_HOP)
    features = np.vstack([chroma, mfcc])  # (18, T)

    # ── Beat tracking ────────────────────────────────────────────
    _, beat_frames = librosa.beat.beat_track(y=y, sr=sr, hop_length=_HOP)
    if len(beat_frames) < 8:
        return []

    beat_times = librosa.frames_to_time(beat_frames, sr=sr, hop_length=_HOP)
    beat_feats = librosa.util.sync(features, beat_frames, aggregate=np.median)

    # ── Agglomerative segmentation ───────────────────────────────
    k = max(2, min(n_target, beat_feats.shape[1] // 4))
    boundary_beat_idx = librosa.segment.agglomerative(beat_feats, k)
    boundary_times_raw = beat_times[boundary_beat_idx]

    all_boundaries = np.concatenate([[0.0], boundary_times_raw, [duration]])

    # ── Build raw section metadata ───────────────────────────────
    raw: list[dict] = []
    for i in range(len(all_boundaries) - 1):
        t0, t1 = float(all_boundaries[i]), float(all_boundaries[i + 1])
        if t1 - t0 < 2.0:
            continue

        # Bar range: first bar at or after t0, last bar starting before t1
        bar_start = next(
            (j for j, b in enumerate(bars) if b["start_sec"] >= t0 - 0.2), 0
        )
        bar_end = len(bars)
        for j in range(len(bars) - 1, -1, -1):
            if bars[j]["start_sec"] < t1 - 0.1:
                bar_end = j + 1
                break

        # Section RMS energy
        f0 = librosa.time_to_frames(t0, sr=sr, hop_length=_HOP)
        f1 = min(librosa.time_to_frames(t1, sr=sr, hop_length=_HOP), rms.shape[1])
        energy = float(np.mean(rms[0, f0:f1])) if f1 > f0 else 0.0

        # Representative feature vector
        b0 = int(np.searchsorted(beat_times, t0))
        b1 = min(int(np.searchsorted(beat_times, t1)), beat_feats.shape[1])
        feat = (
            np.mean(beat_feats[:, b0:b1], axis=1)
            if b1 > b0
            else beat_feats[:, min(b0, beat_feats.shape[1] - 1)]
        )

        raw.append({
            "start": t0, "end": t1,
            "bar_start": bar_start, "bar_end": bar_end,
            "energy": energy, "feat": feat,
        })

    if not raw:
        return []

    # ── Cluster by acoustic similarity ───────────────────────────
    feat_matrix = np.array([s["feat"] for s in raw])
    n_clusters  = max(2, min(4, len(raw)))

    try:
        from sklearn.cluster import KMeans
        km = KMeans(n_clusters=n_clusters, n_init=10, random_state=42)
        cluster_ids: list[int] = km.fit_predict(feat_matrix).tolist()
    except Exception:
        cluster_ids = [0] * len(raw)

    # Letter labels in first-seen order
    letter_map: dict[int, str] = {}
    next_ord = ord("A")
    letters: list[str] = []
    for cid in cluster_ids:
        if cid not in letter_map:
            letter_map[cid] = chr(next_ord)
            next_ord += 1
        letters.append(letter_map[cid])

    # ── Infer section types ──────────────────────────────────────
    counts   = Counter(cluster_ids)
    mean_e   = float(np.mean([s["energy"] for s in raw]))

    type_map: dict[int, str] = {}
    assigned: set[str] = set()
    for rank, (cid, _) in enumerate(sorted(counts.items(), key=lambda x: -x[1])):
        avg_e = float(np.mean([
            s["energy"] for s, c in zip(raw, cluster_ids) if c == cid
        ]))
        if rank == 0:
            t = "chorus" if avg_e >= mean_e else "verse"
        elif rank == 1:
            t = "verse" if "chorus" in assigned else "chorus"
        else:
            t = "bridge"
        type_map[cid] = t
        assigned.add(t)

    # Position-based overrides: short / unique first = intro, last = outro
    total_dur = raw[-1]["end"] - raw[0]["start"]
    result: List[SongSection] = []

    for i, (s, letter, cid) in enumerate(zip(raw, letters, cluster_ids)):
        sec_dur  = s["end"] - s["start"]
        sec_type = type_map.get(cid, "bridge")

        if i == 0 and (sec_dur < total_dur * 0.12 or counts[cid] == 1):
            sec_type = "intro"
        elif i == len(raw) - 1 and (sec_dur < total_dur * 0.12 or counts[cid] == 1):
            sec_type = "outro"

        result.append(SongSection(
            label=letter,
            type=sec_type,
            start_sec=round(s["start"], 3),
            end_sec=round(s["end"], 3),
            bar_start=s["bar_start"],
            bar_end=s["bar_end"],
        ))

    # Guarantee full coverage: first section starts at bar 0, last ends at final bar
    if result:
        result[0].bar_start = 0
        result[-1].bar_end = len(bars)

    return result
