# tests/test_vocal_tab.py
from unittest.mock import patch
from pathlib import Path

import pytest

from pipeline import vocal_tab
from pipeline.transcription import Note
from pipeline.key_detection import KeyEstimate
from pipeline.chord_detection import ChordSegment


def _make_notes(pitches):
    return [Note(pitch=p, start=i * 0.5, end=i * 0.5 + 0.4, velocity=0.8)
            for i, p in enumerate(pitches)]


def _make_bars():
    return [ChordSegment(bar_index=0, start=0.0, end=2.0, label="Am")]


def _make_key():
    return KeyEstimate(tonic="A", mode="minor", correlation=0.9)


def test_should_transpose_high_notes():
    notes = _make_notes([77, 79, 81, 83, 84])  # median=81, above 76 (E5)
    assert vocal_tab._should_transpose(notes) is True


def test_should_not_transpose_low_notes():
    notes = _make_notes([45, 47, 50, 52, 55])  # median=50, below 60
    assert vocal_tab._should_transpose(notes) is False


def test_should_not_transpose_empty():
    assert vocal_tab._should_transpose([]) is False


def test_transcribe_vocal_melody_transposes_when_high():
    high_notes = _make_notes([77, 79, 81, 83, 84])
    with patch("pipeline.vocal_tab.transcribe", return_value=high_notes):
        result_notes, transposed = vocal_tab.transcribe_vocal_melody(Path("fake.wav"))
    assert transposed is True
    assert all(n.pitch == orig.pitch - 12 for n, orig in zip(result_notes, high_notes))


def test_transcribe_vocal_melody_no_transpose_when_low():
    low_notes = _make_notes([45, 47, 50, 52, 55])
    with patch("pipeline.vocal_tab.transcribe", return_value=low_notes):
        result_notes, transposed = vocal_tab.transcribe_vocal_melody(Path("fake.wav"))
    assert transposed is False
    assert all(n.pitch == orig.pitch for n, orig in zip(result_notes, low_notes))


def test_render_vocal_tab_contains_transpose_comment_when_transposed():
    high_notes = _make_notes([77, 79, 81, 83, 84])
    with patch("pipeline.vocal_tab.transcribe", return_value=high_notes):
        result = vocal_tab.render_vocal_tab(
            Path("fake.wav"), _make_bars(), _make_key(), 120.0, "test.wav"
        )
    assert "Transposed: -1 octave" in result


def test_render_vocal_tab_no_transpose_comment_when_not_transposed():
    low_notes = _make_notes([45, 47, 50, 52, 55])
    with patch("pipeline.vocal_tab.transcribe", return_value=low_notes):
        result = vocal_tab.render_vocal_tab(
            Path("fake.wav"), _make_bars(), _make_key(), 120.0, "test.wav"
        )
    assert "Transposed" not in result


def test_should_not_transpose_at_boundary():
    """median == 76 is not > 76, so no transpose (boundary test)."""
    notes = _make_notes([76, 76, 76, 76, 76])
    assert vocal_tab._should_transpose(notes) is False
