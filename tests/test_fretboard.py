from pipeline.fretboard import map_notes_to_fretboard
from pipeline.transcription import Note
from pipeline.tuning import DROP_D, STANDARD_E_A_D_G_B_E, find_tuning


def _note(pitch, start=0.0, end=0.5):
    return Note(start=start, end=end, pitch=pitch, velocity=0.8)


def test_defaults_to_standard_tuning():
    fretted = map_notes_to_fretboard([_note(40)])
    assert len(fretted) == 1
    assert fretted[0].string == 0
    assert fretted[0].fret == 0


def test_low_note_is_dropped_under_standard_tuning():
    fretted = map_notes_to_fretboard([_note(38)], find_tuning(STANDARD_E_A_D_G_B_E))
    assert fretted == []


def test_low_note_is_fretted_under_drop_d_tuning():
    fretted = map_notes_to_fretboard([_note(38)], find_tuning(DROP_D))
    assert len(fretted) == 1
    assert fretted[0].string == 0
    assert fretted[0].fret == 0
