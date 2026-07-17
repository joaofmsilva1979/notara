import pytest

from pipeline.transcription import Note
from pipeline.tuning import (
    DROP_D,
    STANDARD_E_A_D_G_B_E,
    TUNINGS,
    find_tuning,
    fit_score,
    suggest_alternate_tuning,
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


def test_suggest_alternate_tuning_detects_lower_tuning_from_low_notes():
    standard = find_tuning(STANDARD_E_A_D_G_B_E)
    # a riff that repeatedly hits a low D (38), which no string in Standard
    # tuning can produce, alongside notes Standard covers fine
    notes = [_note(38), _note(38), _note(45), _note(50), _note(55), _note(59),
              _note(64), _note(38), _note(45)]
    suggestion = suggest_alternate_tuning(notes, standard)
    assert suggestion is not None
    assert suggestion.suggested.open_string_midi[0] <= 38
    assert suggestion.confidence >= 0.9


def test_suggest_alternate_tuning_returns_none_when_selected_fits_well():
    standard = find_tuning(STANDARD_E_A_D_G_B_E)
    notes = [_note(40), _note(45), _note(50), _note(55), _note(59), _note(64)]
    assert suggest_alternate_tuning(notes, standard) is None


def test_suggest_alternate_tuning_returns_none_when_selected_already_scores_high_enough():
    standard = find_tuning(STANDARD_E_A_D_G_B_E)
    # one low outlier out of ten notes: Standard still scores 0.9, which
    # already meets the confidence bar, so no alternate is even considered
    notes = [_note(38), _note(40), _note(45), _note(50), _note(55), _note(59),
              _note(64), _note(40), _note(45), _note(50)]
    assert suggest_alternate_tuning(notes, standard) is None
