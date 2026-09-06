"""Lyrics forced alignment — aligns provided lyrics to the Demucs vocal stem
using stable-whisper, then overlays detected chord changes above the correct words."""
from __future__ import annotations

import re
from pathlib import Path
from typing import List, Tuple

try:
    import stable_whisper
    _HAS_STABLE_WHISPER = True
except ImportError:
    _HAS_STABLE_WHISPER = False

_SECTION_RE = re.compile(r'^\[.+\]$')
_MIN_CHORD_GAP = 2  # minimum spaces between adjacent chord names on a chord line


def _is_section_label(line: str) -> bool:
    return bool(_SECTION_RE.match(line.strip()))


def _build_chord_line(lyric_line: str, chords_with_pos: List[Tuple[int, str]]) -> str:
    """Build a chord annotation line with names at given character positions.

    Enforces _MIN_CHORD_GAP spaces between adjacent chord names.
    Returns empty string when chords_with_pos is empty.
    """
    if not chords_with_pos:
        return ""

    items = sorted(chords_with_pos, key=lambda x: x[0])
    adjusted: List[Tuple[int, str]] = []
    next_allowed = 0
    for pos, name in items:
        pos = max(pos, next_allowed)
        adjusted.append((pos, name))
        next_allowed = pos + len(name) + _MIN_CHORD_GAP

    chars: List[str] = []
    cursor = 0
    for pos, name in adjusted:
        if pos > cursor:
            chars.append(" " * (pos - cursor))
        chars.append(name)
        cursor = pos + len(name)
    return "".join(chars)


def _char_pos_at_time(
    line: str,
    t_chord: float,
    t_line_start: float,
    t_line_end: float,
) -> int:
    """Estimate the character position in `line` where a chord change at `t_chord` falls."""
    if t_line_end <= t_line_start or not line:
        return 0
    frac = (t_chord - t_line_start) / (t_line_end - t_line_start)
    frac = max(0.0, min(1.0, frac))
    return min(int(frac * len(line)), max(0, len(line) - 1))


def _assign_line_times(
    words: List[Tuple[str, float, float]],
    lyric_lines: List[str],
) -> List[Tuple[str, float, float]]:
    """Map each lyric line to (line, t_start, t_end).

    Content lines consume words sequentially by word count.
    Section labels and blank lines receive t=-1 (no timing assigned).
    """
    result: List[Tuple[str, float, float]] = []
    word_idx = 0
    n_words = len(words)

    for line in lyric_lines:
        stripped = line.strip()
        if not stripped or _is_section_label(stripped):
            result.append((line, -1.0, -1.0))
            continue

        n_line_words = len(stripped.split())
        if word_idx >= n_words or n_line_words == 0:
            result.append((line, -1.0, -1.0))
            continue

        t_start = words[word_idx][1]
        end_idx = min(word_idx + n_line_words - 1, n_words - 1)
        # end_idx is clamped to the last word to absorb alignment drift on the final line
        t_end = words[end_idx][2]
        word_idx = end_idx + 1
        result.append((line, t_start, t_end))

    return result


def align_lyrics(
    lyrics_text: str,
    vocal_stem_path: Path,
    chord_events: list,  # List[ChordSegment] with .start (float) and .label (str)
) -> str:
    """Return a formatted chord chart string with chord labels above each line.

    Graceful fallbacks (all return plain lyrics without chord positions):
    - stable_whisper not installed
    - vocal stem file missing
    - alignment failure

    Returns empty string only when lyrics_text is empty.
    """
    lyrics_text = lyrics_text.strip()
    if not lyrics_text:
        return ""
    if not _HAS_STABLE_WHISPER:
        return lyrics_text  # fallback: plain lyrics, no chord alignment
    if not vocal_stem_path.exists():
        return lyrics_text  # fallback: plain lyrics, no vocal stem

    try:
        model = stable_whisper.load_model("small")
        aligned = model.align(str(vocal_stem_path), lyrics_text, language="en")
        words: List[Tuple[str, float, float]] = [
            (w.word.strip(), w.start, w.end)
            for seg in aligned.segments
            for w in seg.words
        ]
    except Exception:
        return lyrics_text  # fallback: plain lyrics, no chord positions

    if not words:
        return lyrics_text

    lyric_lines = lyrics_text.splitlines()
    line_times = _assign_line_times(words, lyric_lines)

    output: List[str] = []
    for line, t_start, t_end in line_times:
        stripped = line.strip()
        if not stripped:
            output.append("")
            continue
        if _is_section_label(stripped):
            output.append(line)
            continue
        if t_start < 0:
            output.append(line)
            continue

        # Exclusive upper bound: a chord exactly at t_end belongs to the next line
        chords_in_line = [c for c in chord_events if t_start <= c.start < t_end]
        if chords_in_line:
            chords_with_pos = [
                (_char_pos_at_time(line, c.start, t_start, t_end), c.label)
                for c in chords_in_line
            ]
            chord_line = _build_chord_line(line, chords_with_pos)
            if chord_line:
                output.append(chord_line)
        output.append(line)

    return "\n".join(output)
