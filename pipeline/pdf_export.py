"""Step 8 (optional): render the generated tab as a paginated, portrait PDF.

Reuses `tab_render.render_tab`'s already-generated ASCII tab text -- this
module only handles pagination and PDF drawing, it never re-derives note or
chord placement. Forces `bars_per_line=2` regardless of what `bars_per_line`
the .txt export uses, because `tab_render`'s default (4 bars/line, ~197
chars/line) is far too wide to fit a printable A4 page at 7-8pt Courier;
2 bars/line (~99-101 chars/line, depending on tuning string-name length)
fits comfortably at both supported font sizes. HTML->PDF conversion was
deliberately rejected in favor of `reportlab`'s Canvas API (direct,
point-level text placement) for the same reason the original Mac-app design
rejected it: an intermediate layout engine risks subtly misaligning the
monospace ASCII tab columns.

Known limitations:
- Assumes `render_tab`'s body output is always a multiple of 8 lines (1
  chord-label row + 6 string rows + 1 blank separator, repeated) -- true
  today, but a future change to tab_render.py's line-group shape would need
  a matching update here.
- No chord diagram legend (a separate, later chantier).
- Font size is limited to 7 or 8pt. 9pt (5.4pt/char) only leaves ~96
  characters at A4's ~523pt printable width, less than bars_per_line=2's
  ~99-101 characters -- so 9pt is not offered; only 7 and 8pt are
  guaranteed to fit at bars_per_line=2.
- Page size (A4) and margins (36pt) are hardcoded, not CLI-configurable.
"""
from __future__ import annotations

from pathlib import Path
from typing import List

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from .chord_detection import ChordSegment
from .fretboard import FrettedNote
from .key_detection import KeyEstimate
from .tab_render import render_tab
from .tuning import Tuning

import re as _re
from reportlab.lib.colors import HexColor as _HexColor

_, PAGE_HEIGHT = A4  # only page height is used for pagination math; width is fixed by `pagesize=A4` below
MARGIN = 36  # points (0.5 inch)
LINES_PER_BLOCK = 8  # 1 chord-label row + 6 string rows + 1 blank separator
HEADER_LINES_RESERVED = 5  # line-heights reserved at the top of every page for the page header
BARS_PER_LINE_FOR_PDF = 2  # see module docstring for why this differs from tab_render's default


def _line_height(font_size: int) -> float:
    return font_size * 1.15


def _blocks_per_page(font_size: int) -> int:
    """How many whole 8-line tab blocks fit on one A4 page at `font_size`."""
    line_height = _line_height(font_size)
    printable_body_height = PAGE_HEIGHT - 2 * MARGIN - HEADER_LINES_RESERVED * line_height
    lines_per_page = int(printable_body_height // line_height)
    return lines_per_page // LINES_PER_BLOCK


def _split_into_blocks(body_lines: List[str]) -> List[List[str]]:
    """Group `body_lines` into chunks of `LINES_PER_BLOCK` lines each."""
    return [body_lines[i:i + LINES_PER_BLOCK] for i in range(0, len(body_lines), LINES_PER_BLOCK)]


def export_pdf(path: Path, bars: List[ChordSegment], notes: List[FrettedNote],
                key_estimate: KeyEstimate, tempo: float, source_name: str,
                tuning: Tuning, font_size: int = 8) -> None:
    blocks_per_page = _blocks_per_page(font_size)
    if blocks_per_page < 1:
        raise ValueError(
            f"font_size={font_size} leaves no room for even one tab block per "
            f"A4 page with {MARGIN}pt margins -- reduce font_size or increase page size"
        )

    text = render_tab(bars, notes, key_estimate, tempo, source_name, tuning,
                       bars_per_line=BARS_PER_LINE_FOR_PDF)
    all_lines = text.splitlines()
    body_lines = all_lines[8:]  # skip the 7 '#'-comment header lines + 1 blank line
    blocks = _split_into_blocks(body_lines)

    page_groups = [blocks[i:i + blocks_per_page] for i in range(0, len(blocks), blocks_per_page)] or [[]]
    total_pages = len(page_groups)

    pdf = canvas.Canvas(str(path), pagesize=A4)
    line_height = _line_height(font_size)

    for page_number, page_blocks in enumerate(page_groups, start=1):
        y = PAGE_HEIGHT - MARGIN
        pdf.setFont("Courier-Bold", font_size)
        pdf.drawString(MARGIN, y, source_name)
        y -= line_height

        pdf.setFont("Courier", font_size)
        pdf.drawString(MARGIN, y, f"{key_estimate}  |  {tempo:.1f} BPM  |  {tuning.name}")
        y -= line_height

        pdf.drawString(MARGIN, y, f"Page {page_number}/{total_pages}")
        y -= line_height * 2  # blank spacer before the tab body

        for block in page_blocks:
            for line in block:
                pdf.drawString(MARGIN, y, line)
                y -= line_height

        pdf.showPage()

    pdf.save()


_LYRICS_SECTION_RE = _re.compile(r'^\[.+\]$')
_LYRICS_MARGIN_PT = 50
_LYRICS_FONT_PT = 9
_CHORD_LINE_RED = _HexColor("#B71C1C")
_BLACK = _HexColor("#111111")


def _is_chord_annotation_line(line: str) -> bool:
    """Return True if line looks like a chord annotation (no lowercase letters)."""
    stripped = line.strip()
    return bool(stripped) and not any(c.islower() for c in stripped)


def export_lyrics_pdf(path: Path, chord_chart: str) -> None:
    """Render a chord chart string to an A4 PDF.

    Section labels: Courier-Bold 10pt, black.
    Chord annotation lines (no lowercase): Courier-Bold 9pt, red.
    Lyric lines: Courier 9pt, black.
    """
    line_height = _LYRICS_FONT_PT * 1.2
    _, page_height = A4
    lines_per_page = int((page_height - 2 * _LYRICS_MARGIN_PT) / line_height)

    lines = chord_chart.splitlines()
    pdf = canvas.Canvas(str(path), pagesize=A4)
    y = page_height - _LYRICS_MARGIN_PT
    on_page = 0

    for raw_line in lines:
        if on_page >= lines_per_page:
            pdf.showPage()
            y = page_height - _LYRICS_MARGIN_PT
            on_page = 0

        stripped = raw_line.strip()
        if _LYRICS_SECTION_RE.match(stripped):
            pdf.setFont("Courier-Bold", _LYRICS_FONT_PT + 1)
            pdf.setFillColor(_BLACK)
        elif _is_chord_annotation_line(raw_line):
            pdf.setFont("Courier-Bold", _LYRICS_FONT_PT)
            pdf.setFillColor(_CHORD_LINE_RED)
        else:
            pdf.setFont("Courier", _LYRICS_FONT_PT)
            pdf.setFillColor(_BLACK)

        pdf.drawString(_LYRICS_MARGIN_PT, y, raw_line)
        y -= line_height
        on_page += 1

    pdf.save()
