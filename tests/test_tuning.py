import pytest

from pipeline.transcription import Note
from pipeline.tuning import (
    DROP_D,
    STANDARD_E_A_D_G_B_E,
    TUNINGS,
    find_tuning,
    fit_score,
)


def test_tunings_catalog_has_seven_entries():
    assert len(TUNINGS) == 7


def test_find_tuning_returns_standard():
    tuning = find_tuning(STANDARD_E_A_D_G_B_E)
    assert tuning.open_string_midi == [40, 45, 50, 55, 59, 64]
    assert tuning.string_names == ["E", "A", "D", "G", "B", "e"]


def test_find_tuning_returns_drop_d():
    tuning = find_tuning(DROP_D)
    assert tuning.open_string_midi == [38, 45, 50, 55, 59, 64]
    assert tuning.string_names == ["D", "A", "D", "G", "B", "e"]


def test_find_tuning_raises_on_unknown_name():
    with pytest.raises(ValueError):
        find_tuning("Nonexistent Tuning")


def _note(pitch, start=0.0, end=0.5):
    return Note(start=start, end=end, pitch=pitch, velocity=0.8)


def test_fit_score_is_one_when_all_notes_fit():
    tuning = find_tuning(STANDARD_E_A_D_G_B_E)
    notes = [_note(40), _note(45), _note(64)]
    assert fit_score(notes, tuning) == 1.0


def test_fit_score_penalizes_notes_below_lowest_open_string():
    tuning = find_tuning(STANDARD_E_A_D_G_B_E)
    notes = [_note(40), _note(38)]  # 38 (D2) is below open low E (40)
    assert fit_score(notes, tuning) == 0.5


def test_fit_score_is_one_for_empty_notes():
    tuning = find_tuning(STANDARD_E_A_D_G_B_E)
    assert fit_score([], tuning) == 1.0
