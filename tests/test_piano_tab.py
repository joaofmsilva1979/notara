import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from pipeline.piano_tab import render_piano_tab, _notes_to_midi, _notes_to_text


FAKE_NOTES = [
    MagicMock(pitch=60, start=0.0, end=0.5, velocity=0.8),   # C4
    MagicMock(pitch=64, start=0.5, end=1.0, velocity=0.75),  # E4
    MagicMock(pitch=67, start=1.0, end=1.5, velocity=0.7),   # G4
    MagicMock(pitch=72, start=2.0, end=2.5, velocity=0.6),   # C5
]


def test_notes_to_text_returns_string():
    result = _notes_to_text(FAKE_NOTES, bars=4, tempo=120.0)
    assert isinstance(result, str)
    assert len(result) > 0


def test_notes_to_text_contains_note_names():
    result = _notes_to_text(FAKE_NOTES, bars=4, tempo=120.0)
    assert "C4" in result or "C5" in result or "E4" in result


def test_notes_to_midi_returns_bytes():
    result = _notes_to_midi(FAKE_NOTES, tempo=120.0)
    assert isinstance(result, bytes)
    # If mido is installed, should be a valid MIDI file; if not, empty bytes
    if result:
        assert result[:4] == b"MThd"


def test_render_piano_tab_no_stem_returns_none(tmp_path):
    missing = tmp_path / "nonexistent.wav"
    result = render_piano_tab(missing, bars=32, key_est="C major", tempo=120.0, source_name="test")
    assert result is None


@patch("pipeline.piano_tab.transcribe")
def test_render_piano_tab_returns_dict(mock_transcribe, tmp_path):
    stem = tmp_path / "piano.wav"
    stem.write_bytes(b"\x00" * 100)
    mock_transcribe.return_value = FAKE_NOTES
    result = render_piano_tab(stem, bars=32, key_est="C major", tempo=120.0, source_name="piano")
    assert result is not None
    assert "text" in result
    assert "midi_bytes" in result
    assert isinstance(result["text"], str)
    assert isinstance(result["midi_bytes"], bytes)


@patch("pipeline.piano_tab.transcribe")
def test_render_piano_tab_empty_notes_returns_none(mock_transcribe, tmp_path):
    stem = tmp_path / "piano.wav"
    stem.write_bytes(b"\x00" * 100)
    mock_transcribe.return_value = []
    result = render_piano_tab(stem, bars=32, key_est="C major", tempo=120.0, source_name="piano")
    assert result is None
