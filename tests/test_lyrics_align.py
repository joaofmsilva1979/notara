import pytest
from pipeline.lyrics_align import (
    _is_section_label,
    _build_chord_line,
    _char_pos_at_time,
    align_lyrics,
)


def test_is_section_label_matches():
    assert _is_section_label("[Verse 1]") is True
    assert _is_section_label("[Chorus]") is True
    assert _is_section_label("[Bridge]") is True


def test_is_section_label_rejects():
    assert _is_section_label("Hello world") is False
    assert _is_section_label("[incomplete") is False
    assert _is_section_label("") is False


def test_build_chord_line_basic():
    line = "Hello world foo bar"
    chords = [(0, "Am"), (6, "G")]
    result = _build_chord_line(line, chords)
    assert result.startswith("Am")
    assert "G" in result


def test_build_chord_line_no_overlap():
    line = "Hello world"
    chords = [(0, "Am"), (1, "G")]
    result = _build_chord_line(line, chords)
    am_pos = result.index("Am")
    g_pos = result.index("G")
    assert g_pos >= am_pos + len("Am") + 2


def test_build_chord_line_empty_chords():
    assert _build_chord_line("Hello world", []) == ""


def test_char_pos_at_line_start():
    pos = _char_pos_at_time("Hello world", t_chord=0.0, t_line_start=0.0, t_line_end=2.0)
    assert pos == 0


def test_char_pos_at_line_midpoint():
    pos = _char_pos_at_time("Hello world", t_chord=1.0, t_line_start=0.0, t_line_end=2.0)
    assert pos == 5


def test_align_lyrics_empty_input(tmp_path):
    dummy = tmp_path / "vocals.wav"
    dummy.touch()
    assert align_lyrics("", dummy, []) == ""


def test_align_lyrics_missing_stem(tmp_path):
    assert align_lyrics("Hello world", tmp_path / "missing.wav", []) == ""


def test_align_lyrics_no_stable_whisper(monkeypatch, tmp_path):
    import pipeline.lyrics_align as la
    monkeypatch.setattr(la, "_HAS_STABLE_WHISPER", False)
    dummy = tmp_path / "vocals.wav"
    dummy.touch()
    assert la.align_lyrics("Hello world", dummy, []) == ""
