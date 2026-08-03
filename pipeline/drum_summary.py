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
    if sr // 2 <= HIHAT_LO:
        hihat = 0.0  # hi-hat band unreachable at this sample rate
    else:
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
        if bar_idx < 0 or bar_idx >= n_bars:
            continue
        pos_in_bar = (t % bar_sec) / bar_sec
        slot = int(pos_in_bar * GRID_SUBDIVISIONS)  # floor — musically cleaner
        slot = min(slot, GRID_SUBDIVISIONS - 1)
        grid[label][bar_idx][slot] = "●"
    return grid


def _ascii_pattern(grid: dict) -> str:
    n_bars = len(grid["K"])
    header = "Beat:  1    +    2    +    3    +    4    +"
    lines = []
    for bar_idx in range(n_bars):
        lines.append(f"Bar {bar_idx + 1}: {header}")
        for inst, prefix in (("K", "K:"), ("S", "S:"), ("H", "HH:")):
            row = grid[inst][bar_idx]
            cells = [f"{c:<5}" for c in row]
            lines.append(f"  {prefix:<6}" + "".join(cells))
        if bar_idx < n_bars - 1:
            lines.append("")
    return "\n".join(lines)


def _pattern_description(grid: dict, tempo: float) -> str:
    n_bars = len(grid["K"])
    # Aggregate hits across all bars for the pattern description
    k_slots = [i for bar_idx in range(n_bars) for i, c in enumerate(grid["K"][bar_idx]) if c == "●"]
    s_slots = [i for bar_idx in range(n_bars) for i, c in enumerate(grid["S"][bar_idx]) if c == "●"]
    h_slots = [i for bar_idx in range(n_bars) for i, c in enumerate(grid["H"][bar_idx]) if c == "●"]

    parts = [f"4/4 · {tempo:.0f} BPM"]
    if k_slots:
        beats = sorted({i // 2 + 1 for i in k_slots})
        parts.append("kick on " + "&".join(str(b) for b in beats))
    if s_slots:
        beats = sorted({i // 2 + 1 for i in s_slots})
        parts.append("snare on " + "&".join(str(b) for b in beats))
    h_count = len(h_slots) // n_bars  # average per bar
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
