"""Classify each bar as 'melody' (monophonic) or 'chord' (polyphonic).

Samples instantaneous note polyphony at multiple points inside each bar
and computes the mean. Below the threshold → melody / solo; above → chords.
"""
from __future__ import annotations

from typing import List


def classify_bars(
    notes: list,          # List[FrettedNote] — need .start, .end, .pitch
    bars: list,           # list of dicts with 'start_sec' / 'end_sec'
    poly_threshold: float = 1.6,
    n_samples: int = 16,
) -> List[str]:
    """
    Return a list of 'melody' | 'chord' labels, one per bar.

    A bar is considered 'melody' if the average number of simultaneously
    active notes is below `poly_threshold`. This catches single-note runs,
    solos, and monophonic vocal lines, distinguishing them from strummed
    chords or full-band textures.
    """
    result: List[str] = []

    for bar in bars:
        t0 = bar["start_sec"]
        t1 = bar["end_sec"]

        if t1 <= t0:
            result.append("chord")
            continue

        bar_notes = [n for n in notes if n.start >= t0 - 0.05 and n.start < t1 + 0.05]

        if not bar_notes:
            result.append("chord")
            continue

        dur = t1 - t0
        total_active = 0
        for i in range(n_samples):
            t = t0 + (i / n_samples) * dur
            active = sum(1 for n in bar_notes if n.start <= t <= n.end)
            total_active += active

        avg = total_active / n_samples
        result.append("melody" if avg < poly_threshold else "chord")

    return result
