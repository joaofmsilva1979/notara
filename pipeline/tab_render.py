"""Step 6: render fretted notes + chords + key into a classic 6-line ASCII tab.

Each bar (taken from chord_detection's beat-synchronous bars) is rendered as
a fixed-width grid of COLUMNS_PER_BAR slots (a 16th-note grid, assuming 4/4
-- same assumption as chord_detection). Notes are snapped to the nearest
slot; the chord label detected for that bar is printed above it.

Known limitations:
- Rhythm is only approximate: ASCII tab shows fret position, not note
  duration, so two notes snapped to adjacent slots look identical whether
  the original was a quarter note or a triplet. The fixed 16-slot/bar grid
  will misrepresent anything that isn't roughly 16th-note-aligned in 4/4
  (swing, triplets, odd meters, tempo changes).
- If two notes land in the same slot on the same string (e.g. transcription
  produced overlapping notes), the later one silently overwrites the
  earlier one in that cell.
"""
from __future__ import annotations

from pathlib import Path
from typing import List

from .chord_detection import ChordSegment
from .fretboard import FrettedNote
from .key_detection import KeyEstimate
from .tuning import STANDARD_E_A_D_G_B_E, Tuning, find_tuning

COLUMNS_PER_BAR = 16
CELL_WIDTH = 3


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


def write_tab(path: Path, bars: List[ChordSegment], notes: List[FrettedNote],
              key_estimate: KeyEstimate, tempo: float, source_name: str,
              tuning: Tuning = None) -> None:
    text = render_tab(bars, notes, key_estimate, tempo, source_name, tuning)
    path.write_text(text, encoding="utf-8")
