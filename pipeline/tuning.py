"""Guitar tuning catalog.

Tunings are represented as open-string MIDI pitches, ordered from the
lowest-pitched string to the highest-pitched string -- the same convention
`fretboard.py` uses for its fretting logic. `MAX_FRET` (the highest fret
position the pipeline will consider when fretting a note) lives here rather
than in `fretboard.py` so that tuning fit-scoring (see the `fit_score`
function added in a later step) does not need to import from `fretboard`,
which avoids a circular import between the two modules.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from .transcription import Note

MAX_FRET = 15

STANDARD_E_A_D_G_B_E = "Standard EADGBE"
DROP_D = "Drop D"
EB_STANDARD = "Eb Standard"
D_STANDARD = "D Standard"
DROP_C_SHARP = "Drop C#"
OPEN_G = "Open G"
OPEN_D = "Open D"
BASS_STANDARD_EADG = "Bass Standard EADG"
BASS_DROP_D = "Bass Drop D"
BASS_5_STRING_BEADG = "Bass 5-String BEADG"

C_SHARP_STANDARD = "C# Standard"
C_STANDARD = "C Standard"
DROP_C = "Drop C"
DROP_B = "Drop B"
DROP_A = "Drop A"
OPEN_E = "Open E"
OPEN_A = "Open A"
OPEN_C = "Open C"
DADGAD = "DADGAD"
BARITONE_B = "Baritone B"
BARITONE_A = "Baritone A"

SEVEN_STRING_STANDARD = "7-String Standard"
SEVEN_STRING_DROP_A = "7-String Drop A"
EIGHT_STRING_STANDARD = "8-String Standard"
EIGHT_STRING_DROP_E = "8-String Drop E"


@dataclass(frozen=True)
class Tuning:
    name: str
    open_string_midi: List[int]  # lowest string to highest string
    string_names: List[str]


TUNINGS: List[Tuning] = [
    Tuning(STANDARD_E_A_D_G_B_E, [40, 45, 50, 55, 59, 64], ["E", "A", "D", "G", "B", "e"]),
    Tuning(DROP_D,               [38, 45, 50, 55, 59, 64], ["D", "A", "D", "G", "B", "e"]),
    Tuning(EB_STANDARD,          [39, 44, 49, 54, 58, 63], ["Eb", "Ab", "Db", "Gb", "Bb", "eb"]),
    Tuning(D_STANDARD,           [38, 43, 48, 53, 57, 62], ["D", "G", "C", "F", "A", "d"]),
    Tuning(DROP_C_SHARP,         [37, 44, 49, 54, 58, 63], ["C#", "Ab", "Db", "Gb", "Bb", "eb"]),
    Tuning(OPEN_G,               [38, 43, 50, 55, 59, 62], ["D", "G", "D", "G", "B", "d"]),
    Tuning(OPEN_D,               [38, 45, 50, 54, 57, 62], ["D", "A", "D", "F#", "A", "d"]),
    # New 6-string tunings
    Tuning(C_SHARP_STANDARD,     [37, 42, 47, 52, 56, 61], ["C#", "F#", "B", "E", "G#", "c#"]),
    Tuning(C_STANDARD,           [36, 41, 46, 51, 55, 60], ["C", "F", "Bb", "Eb", "G", "c"]),
    Tuning(DROP_C,               [36, 43, 48, 53, 57, 62], ["C", "G", "C", "F", "A", "d"]),
    Tuning(DROP_B,               [35, 42, 47, 52, 56, 61], ["B", "F#", "B", "E", "G#", "c#"]),
    Tuning(DROP_A,               [33, 40, 45, 50, 54, 59], ["A", "E", "A", "D", "F#", "b"]),
    Tuning(OPEN_E,               [40, 47, 52, 56, 59, 64], ["E", "B", "E", "G#", "B", "e"]),
    Tuning(OPEN_A,               [40, 45, 52, 57, 61, 64], ["E", "A", "E", "A", "C#", "e"]),
    Tuning(OPEN_C,               [36, 43, 48, 55, 60, 64], ["C", "G", "C", "G", "C", "e"]),
    Tuning(DADGAD,               [38, 45, 50, 55, 57, 62], ["D", "A", "D", "G", "A", "d"]),
    Tuning(BARITONE_B,           [35, 40, 45, 50, 54, 59], ["B", "E", "A", "D", "F#", "b"]),
    Tuning(BARITONE_A,           [33, 38, 43, 48, 52, 57], ["A", "D", "G", "C", "E", "a"]),
]

EXTENDED_TUNINGS: List[Tuning] = [
    Tuning(SEVEN_STRING_STANDARD, [35, 40, 45, 50, 55, 59, 64], ["B", "E", "A", "D", "G", "B", "e"]),
    Tuning(SEVEN_STRING_DROP_A,   [33, 40, 45, 50, 55, 59, 64], ["A", "E", "A", "D", "G", "B", "e"]),
    Tuning(EIGHT_STRING_STANDARD, [30, 35, 40, 45, 50, 55, 59, 64], ["F#", "B", "E", "A", "D", "G", "B", "e"]),
    Tuning(EIGHT_STRING_DROP_E,   [28, 35, 40, 45, 50, 55, 59, 64], ["E", "B", "E", "A", "D", "G", "B", "e"]),
]


# Bass tunings kept separate so suggest_alternate_tuning never proposes a
# bass tuning as an alternative for a guitar track.
BASS_TUNINGS: List[Tuning] = [
    Tuning(BASS_STANDARD_EADG, [28, 33, 38, 43], ["E", "A", "D", "G"]),
    Tuning(BASS_DROP_D, [26, 33, 38, 43], ["D", "A", "D", "G"]),
    Tuning(BASS_5_STRING_BEADG, [23, 28, 33, 38, 43], ["B", "E", "A", "D", "G"]),
]


def find_tuning(name: str) -> Tuning:
    for tuning in TUNINGS + BASS_TUNINGS + EXTENDED_TUNINGS:
        if tuning.name == name:
            return tuning
    raise ValueError(f"Unknown tuning: {name!r}")


def _fits(pitch: int, tuning: Tuning) -> bool:
    return any(0 <= pitch - open_midi <= MAX_FRET for open_midi in tuning.open_string_midi)


def fit_score(notes: List[Note], tuning: Tuning) -> float:
    """Fraction of `notes` that CAN be fretted on `tuning` within [0, MAX_FRET].

    Notes below every string's open pitch (i.e. would need a negative fret)
    are the strongest signal of a mismatched tuning -- e.g. a recurring low
    D under an assumed Standard tuning, where no string can produce it.
    """
    if not notes:
        return 1.0
    fitting = sum(1 for note in notes if _fits(note.pitch, tuning))
    return fitting / len(notes)


@dataclass
class TuningSuggestion:
    suggested: Tuning
    confidence: float


def suggest_alternate_tuning(notes: List[Note], selected: Tuning,
                              min_confidence: float = 0.9,
                              min_improvement: float = 0.1,
                              min_notes: int = 8) -> Optional[TuningSuggestion]:
    """Return a better-fitting tuning if one clearly explains `notes` better
    than `selected`, else None.

    "Clearly better" means: the candidate scores at least `min_confidence`,
    AND it beats `selected`'s score by at least `min_improvement`. If ties
    occur between candidates, the first one encountered in `TUNINGS` wins --
    this pipeline cannot distinguish tunings that happen to fit the same set
    of notes equally well (e.g. a song that never touches its lowest string
    sounds identical in Drop D and D Standard).

    Also returns None if there aren't at least `min_notes` transcribed notes
    to base a suggestion on -- a handful of notes isn't enough signal to
    trust the fit-score ratio (with only 1-2 notes, `fit_score` can only ever
    be 0, 0.5, or 1.0, so a single spurious note -- e.g. a separation
    artifact from basic-pitch -- could otherwise produce a maximally
    "confident"-looking suggestion).
    """
    if len(notes) < min_notes:
        return None  # not enough signal to trust the fit-score ratio

    selected_score = fit_score(notes, selected)
    if selected_score >= min_confidence:
        return None  # selected tuning already explains the notes well

    best: Optional[TuningSuggestion] = None
    for tuning in TUNINGS:
        if tuning.name == selected.name:
            continue
        score = fit_score(notes, tuning)
        if score >= min_confidence and score - selected_score >= min_improvement:
            if best is None or score > best.confidence:
                best = TuningSuggestion(suggested=tuning, confidence=score)
    return best
