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
from typing import List

from .transcription import Note

MAX_FRET = 15

STANDARD_E_A_D_G_B_E = "Standard EADGBE"
DROP_D = "Drop D"
EB_STANDARD = "Eb Standard"
D_STANDARD = "D Standard"
DROP_C_SHARP = "Drop C#"
OPEN_G = "Open G"
OPEN_D = "Open D"


@dataclass(frozen=True)
class Tuning:
    name: str
    open_string_midi: List[int]  # lowest string to highest string, 6 values
    string_names: List[str]


TUNINGS: List[Tuning] = [
    Tuning(STANDARD_E_A_D_G_B_E, [40, 45, 50, 55, 59, 64], ["E", "A", "D", "G", "B", "e"]),
    Tuning(DROP_D, [38, 45, 50, 55, 59, 64], ["D", "A", "D", "G", "B", "e"]),
    Tuning(EB_STANDARD, [39, 44, 49, 54, 58, 63], ["Eb", "Ab", "Db", "Gb", "Bb", "eb"]),
    Tuning(D_STANDARD, [38, 43, 48, 53, 57, 62], ["D", "G", "C", "F", "A", "d"]),
    Tuning(DROP_C_SHARP, [37, 44, 49, 54, 58, 63], ["C#", "Ab", "Db", "Gb", "Bb", "eb"]),
    Tuning(OPEN_G, [38, 43, 50, 55, 59, 62], ["D", "G", "D", "G", "B", "d"]),
    Tuning(OPEN_D, [38, 45, 50, 54, 57, 62], ["D", "A", "D", "F#", "A", "d"]),
]


def find_tuning(name: str) -> Tuning:
    for tuning in TUNINGS:
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
