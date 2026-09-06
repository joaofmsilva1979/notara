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
    chords = [(0, "Am"), (10, "G")]
    result = _build_chord_line(line, chords)
    assert result.index("Am") == 0
    assert result.index("G") == 10


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
    # No vocal stem → graceful fallback: return plain lyrics without chord positions
    assert align_lyrics("Hello world", tmp_path / "missing.wav", []) == "Hello world"


def test_align_lyrics_no_stable_whisper(monkeypatch, tmp_path):
    import pipeline.lyrics_align as la
    monkeypatch.setattr(la, "_HAS_STABLE_WHISPER", False)
    dummy = tmp_path / "vocals.wav"
    dummy.touch()
    # stable_whisper not installed → graceful fallback: return plain lyrics without alignment
    assert la.align_lyrics("Hello world", dummy, []) == "Hello world"


def test_char_pos_at_line_end_clamped():
    # t_chord at t_line_end (frac=1.0) must not exceed len(line)-1
    line = "Hello world"
    pos = _char_pos_at_time(line, t_chord=2.0, t_line_start=0.0, t_line_end=2.0)
    assert pos < len(line)


def test_assign_line_times_section_labels_get_no_timing():
    from pipeline.lyrics_align import _assign_line_times
    words = [("hello", 0.0, 0.5), ("world", 0.5, 1.0)]
    lines = ["[Verse 1]", "hello world"]
    result = _assign_line_times(words, lines)
    assert result[0] == ("[Verse 1]", -1.0, -1.0)
    assert result[1][1] == 0.0
    assert result[1][2] == 1.0


def test_assign_line_times_blank_lines_get_no_timing():
    from pipeline.lyrics_align import _assign_line_times
    words = [("hello", 0.0, 0.5)]
    lines = ["", "hello"]
    result = _assign_line_times(words, lines)
    assert result[0] == ("", -1.0, -1.0)
    assert result[1][1] == 0.0
