"""Unit tests for pipeline/transcription_synthtab.py.

All tests mock the SynthTab model — no model weights are loaded.
"""
import numpy as np
import pytest
from unittest.mock import MagicMock, patch
from pipeline import transcription_synthtab
from pipeline.transcription import Note


@pytest.fixture(autouse=True)
def _mock_synthtab(monkeypatch):
    """Inject a pre-loaded model and CQT so _load() is a no-op."""
    mock_model = MagicMock()
    mock_model.device = "cpu"
    mock_model.parameters.return_value = iter([MagicMock()])
    mock_model.pre_proc.side_effect = lambda b: b
    mock_model.post_proc.side_effect = lambda b: b

    import torch
    mock_model.return_value = torch.full((1, 10, 6, 1), -1, dtype=torch.int64)

    mock_cqt = MagicMock()
    mock_cqt.process_audio.return_value = np.zeros((1, 192, 10))

    monkeypatch.setattr(transcription_synthtab, "_model", mock_model)
    monkeypatch.setattr(transcription_synthtab, "_cqt", mock_cqt)


# ── _tab_to_notes ─────────────────────────────────────────────────────────────

def test_tab_to_notes_muted_string_no_note():
    tab = np.full((10, 6), -1)
    assert transcription_synthtab._tab_to_notes(tab) == []

def test_tab_to_notes_open_low_e():
    # String 0 (low E) fret 0 for 5 frames → MIDI 40
    tab = np.full((10, 6), -1)
    tab[:5, 0] = 0
    notes = transcription_synthtab._tab_to_notes(tab)
    assert len(notes) == 1
    assert notes[0].pitch == 40  # open low E

def test_tab_to_notes_fret_adds_to_open():
    # String 0 fret 5 for 5 frames → MIDI 40 + 5 = 45 (A)
    tab = np.full((10, 6), -1)
    tab[:5, 0] = 5
    notes = transcription_synthtab._tab_to_notes(tab)
    assert len(notes) == 1
    assert notes[0].pitch == 45

def test_tab_to_notes_short_note_dropped():
    # 1 frame at _HOP_LENGTH/SR ≈ 0.023 s — below _MIN_NOTE_SEC (0.08 s)
    tab = np.full((20, 6), -1)
    tab[0, 0] = 2
    notes = transcription_synthtab._tab_to_notes(tab)
    assert all(n.pitch != 42 for n in notes)

def test_tab_to_notes_multiple_strings():
    tab = np.full((10, 6), -1)
    tab[:5, 0] = 0   # E (MIDI 40)
    tab[:5, 2] = 2   # D string fret 2 = F# (MIDI 52)
    notes = transcription_synthtab._tab_to_notes(tab)
    pitches = {n.pitch for n in notes}
    assert 40 in pitches
    assert 52 in pitches

def test_tab_to_notes_sorted_by_start():
    tab = np.full((20, 6), -1)
    tab[10:15, 0] = 0   # starts at frame 10
    tab[:5, 1] = 0      # starts at frame 0
    notes = transcription_synthtab._tab_to_notes(tab)
    starts = [n.start for n in notes]
    assert starts == sorted(starts)

def test_tab_to_notes_velocity_is_fixed():
    tab = np.full((10, 6), -1)
    tab[:5, 0] = 0
    notes = transcription_synthtab._tab_to_notes(tab)
    assert all(n.velocity == transcription_synthtab._MIN_VELOCITY for n in notes)

def test_open_string_midi_pitches():
    # Verify the open string MIDI mapping matches standard EADGBE
    expected = [40, 45, 50, 55, 59, 64]
    assert transcription_synthtab._OPEN_STRING_MIDI == expected
