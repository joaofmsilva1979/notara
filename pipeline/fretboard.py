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
POSITION_SPAN = 5  # fret span of one neck position (e.g. frets 5–9)


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
    """Default placement: whole-phrase optimisation (see map_notes_to_fretboard_dp).

    GuitarSet, held-out players 03-05: greedy 55.3% -> dp 63.7% notes on the
    right string+fret (tests/benchmark_tab.py fingering).
    """
    return map_notes_to_fretboard_dp(notes, tuning)


def map_notes_to_fretboard_greedy(notes: List[Note], tuning: Optional[Tuning] = None) -> List[FrettedNote]:
    """Previous note-by-note heuristic, kept as the benchmark baseline."""
    if tuning is None:
        tuning = find_tuning(STANDARD_E_A_D_G_B_E)
    fretted: List[FrettedNote] = []
    position_start = 0  # left edge of the current 4-fret position window

    for group in _group_by_onset(notes):
        used_strings: set = set()
        # Assign highest pitches first: they have fewer valid strings/frets,
        # so giving them first pick reduces collisions.
        for note in sorted(group, key=lambda n: -n.pitch):
            chosen: Optional[tuple] = None

            # First pass: prefer frets within the current window, or open strings
            for string_idx, fret in _fret_options(note.pitch, tuning):
                if string_idx not in used_strings:
                    if fret == 0 or position_start <= fret <= position_start + POSITION_SPAN:
                        chosen = (string_idx, fret)
                        break

            # Second pass: fall back to lowest available fret on any free string
            if chosen is None:
                for string_idx, fret in _fret_options(note.pitch, tuning):
                    if string_idx not in used_strings:
                        chosen = (string_idx, fret)
                        break

            if chosen is None:
                continue  # out of range or no free string left; note dropped

            string_idx, fret = chosen
            used_strings.add(string_idx)

            # Shift window only when a non-open fret lands outside it
            if fret > 0 and not (position_start <= fret <= position_start + POSITION_SPAN):
                position_start = max(0, fret - 1)

            fretted.append(FrettedNote(
                string=string_idx, fret=fret,
                start=note.start, end=note.end, pitch=note.pitch,
            ))

    fretted.sort(key=lambda fn: fn.start)
    return fretted


# ── Whole-phrase fingering (dynamic programming) ─────────────────────────────
# Instead of choosing each note greedily, pick for every onset group the
# fingering that minimises (static difficulty of the grasp + hand movement
# from the previous grasp) over the whole piece — a Viterbi pass.

W_SPAN = 1.0        # per fret of stretch beyond a comfortable span
COMFORT_SPAN = 3    # index→pinky span with no penalty
W_HEIGHT = 0.05     # slight preference for lower positions
W_MOVE = 0.6        # per fret of hand shift between grasps
W_OPEN = -0.1       # small bonus for open strings (easy, idiomatic)
MAX_CANDIDATES = 60


def _grasp_candidates(group: List[Note], tuning: Tuning) -> List[List[tuple]]:
    """All ways to play the group with one note per string (pruned)."""
    notes = sorted(group, key=lambda n: -n.pitch)
    partial: List[List[tuple]] = [[]]
    for note in notes:
        opts = _fret_options(note.pitch, tuning)
        nxt = []
        for cand in partial:
            used = {s for s, _, _ in cand}
            for s, f in opts:
                if s not in used:
                    nxt.append(cand + [(s, f, note)])
        if not nxt:  # unplayable note (range / strings exhausted): drop it
            continue
        nxt.sort(key=_static_cost)
        partial = nxt[:MAX_CANDIDATES]
    return [c for c in partial if c]


def _static_cost(cand: List[tuple]) -> float:
    fretted = [f for _, f, _ in cand if f > 0]
    cost = W_OPEN * (len(cand) - len(fretted))
    if fretted:
        span = max(fretted) - min(fretted)
        cost += W_SPAN * max(0, span - COMFORT_SPAN) ** 2 + W_HEIGHT * min(fretted)
    return cost


def _hand(cand: List[tuple]) -> Optional[float]:
    # Mean fretted position: measured slightly better than min fret on GuitarSet.
    fretted = [f for _, f, _ in cand if f > 0]
    return sum(fretted) / len(fretted) if fretted else None


def map_notes_to_fretboard_dp(notes: List[Note], tuning: Optional[Tuning] = None) -> List[FrettedNote]:
    if tuning is None:
        tuning = find_tuning(STANDARD_E_A_D_G_B_E)
    layers = [c for c in (_grasp_candidates(g, tuning) for g in _group_by_onset(notes)) if c]
    if not layers:
        return []

    # Viterbi; hand position carries through all-open grasps.
    cost = [_static_cost(c) for c in layers[0]]
    hand = [_hand(c) for c in layers[0]]
    back: List[List[int]] = []
    for layer in layers[1:]:
        new_cost, new_hand, ptr = [], [], []
        for cand in layer:
            h = _hand(cand)
            best_i, best = 0, float("inf")
            for i, (pc, ph) in enumerate(zip(cost, hand)):
                move = abs(h - ph) if (h is not None and ph is not None) else 0.0
                total = pc + W_MOVE * move
                if total < best:
                    best_i, best = i, total
            new_cost.append(best + _static_cost(cand))
            new_hand.append(h if h is not None else hand[best_i])
            ptr.append(best_i)
        cost, hand = new_cost, new_hand
        back.append(ptr)

    i = min(range(len(cost)), key=cost.__getitem__)
    chosen = [layers[-1][i]]
    for k in range(len(back) - 1, -1, -1):
        i = back[k][i]
        chosen.append(layers[k][i])
    chosen.reverse()

    out = [FrettedNote(string=s, fret=f, start=n.start, end=n.end, pitch=n.pitch)
           for cand in chosen for s, f, n in cand]
    out.sort(key=lambda fn: fn.start)
    return out
