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
from reportlab.lib.colors import HexColor as _HexColor, white as _white, black as _black

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


# ── Rehearsal cheat sheet ────────────────────────────────────────────────────

_RS_COLORS = {
    "intro":  _HexColor("#888888"),
    "verse":  _HexColor("#2C5F8A"),
    "chorus": _HexColor("#B71C1C"),
    "bridge": _HexColor("#2E7D32"),
    "outro":  _HexColor("#666666"),
}
_RS_LABELS = {
    "intro": "INTRO", "verse": "COUPLET",
    "chorus": "REFRAIN", "bridge": "PONT", "outro": "OUTRO",
}
_RS_MARGIN = 40
_RS_SEC_H = 20
_RS_ROW_H = 32        # height of each measure row (more compact than old _RS_CELL_H=44)
_RS_BARS_PER_ROW = 4
_RS_REPEAT_W = 28     # width reserved to the right for "×N" markers


def export_rehearsal_pdf(
    path: Path,
    title: str,
    key_str: str,
    tempo: float,
    tuning_name: str,
    bars: list,      # list of dicts: {'label', 'start_sec', 'end_sec'}
    sections: list,  # list of dicts: {'type', 'label', 'bar_start', 'bar_end'}
) -> None:
    """Rehearsal cheat sheet — linear chord chart with bar separators and repeat compression.

    Each section renders as horizontal rows: | Chord1  | Chord2  | Chord3  | Chord4  ||
    Consecutive rows with the same chord pattern are collapsed: one row shown + ×N marker.
    """
    PAGE_W, PAGE_H = A4
    BODY_W = PAGE_W - 2 * _RS_MARGIN - _RS_REPEAT_W
    CELL_W = BODY_W / _RS_BARS_PER_ROW

    pdf = canvas.Canvas(str(path), pagesize=A4)
    y = PAGE_H - _RS_MARGIN

    def _new_page() -> float:
        pdf.showPage()
        return PAGE_H - _RS_MARGIN

    def _ensure(needed: float) -> None:
        nonlocal y
        if y - needed < _RS_MARGIN:
            y = _new_page()

    # ── Header ──────────────────────────────────────────────────
    short = title[:55] + "…" if len(title) > 55 else title
    pdf.setFont("Helvetica-Bold", 13)
    pdf.setFillColor(_black)
    pdf.drawString(_RS_MARGIN, y, short)
    y -= 15

    pdf.setFont("Helvetica", 8)
    pdf.setFillColor(_HexColor("#666666"))
    pdf.drawString(_RS_MARGIN, y, f"Clé : {key_str}   ·   {tempo} BPM   ·   {tuning_name}   ·   Notara")
    y -= 7
    pdf.setStrokeColor(_HexColor("#CCCCCC"))
    pdf.line(_RS_MARGIN, y, PAGE_W - _RS_MARGIN, y)
    y -= 12

    # ── Sections ────────────────────────────────────────────────
    for section in sections:
        sec_bars = bars[section["bar_start"]: section["bar_end"]]
        if not sec_bars:
            continue

        color   = _RS_COLORS.get(section["type"], _HexColor("#888888"))
        display = _RS_LABELS.get(section["type"], section["type"].upper())

        # Group bars into rows of _RS_BARS_PER_ROW
        rows = []
        for i in range(0, len(sec_bars), _RS_BARS_PER_ROW):
            chunk = sec_bars[i: i + _RS_BARS_PER_ROW]
            nums  = [section["bar_start"] + i + j + 1 for j in range(len(chunk))]
            key   = tuple(b.get("label") or "N.C." for b in chunk)
            rows.append([key, nums, chunk, 1])   # [chord_key, bar_nums, bars, repeat_count]

        # Collapse consecutive identical rows
        collapsed: list = []
        for row in rows:
            if collapsed and collapsed[-1][0] == row[0]:
                collapsed[-1][3] += 1
            else:
                collapsed.append(row)

        # Section header
        _ensure(_RS_SEC_H + _RS_ROW_H)
        pdf.setFillColor(color)
        pdf.rect(_RS_MARGIN, y - _RS_SEC_H, PAGE_W - 2 * _RS_MARGIN, _RS_SEC_H, fill=1, stroke=0)
        pdf.setFillColor(_white)
        pdf.setFont("Helvetica-Bold", 8)
        pdf.drawString(_RS_MARGIN + 6, y - _RS_SEC_H + 6, display)
        lbl = f"({section['label']})"
        lbl_w = pdf.stringWidth(lbl, "Helvetica-Bold", 8)
        pdf.drawString(PAGE_W - _RS_MARGIN - lbl_w - 6, y - _RS_SEC_H + 6, lbl)
        y -= _RS_SEC_H

        # Draw rows — chord chart style: no cell fills, vertical bar lines only
        BAR_LINE_H = _RS_ROW_H - 4   # bar lines don't touch the horizontal row lines
        BAR_LINE_Y_TOP = 0            # will be computed per row

        for row_idx, (chord_key, bar_nums, chunk, repeat_count) in enumerate(collapsed):
            _ensure(_RS_ROW_H + 2)

            row_y = y  # top of this row
            mid_y  = row_y - _RS_ROW_H / 2

            # Thin horizontal lines — top and bottom of row (staff-line feel)
            pdf.setStrokeColor(_HexColor("#CCCCCC"))
            pdf.setLineWidth(0.4)
            pdf.line(_RS_MARGIN, row_y,              _RS_MARGIN + BODY_W, row_y)
            pdf.line(_RS_MARGIN, row_y - _RS_ROW_H, _RS_MARGIN + BODY_W, row_y - _RS_ROW_H)

            # Vertical bar lines (musical bar lines)
            bar_top = row_y - 2
            bar_bot = row_y - _RS_ROW_H + 2

            # Opening double bar ||
            pdf.setStrokeColor(_HexColor("#444444"))
            pdf.setLineWidth(0.5)
            pdf.line(_RS_MARGIN,     bar_top, _RS_MARGIN,     bar_bot)
            pdf.setLineWidth(1.5)
            pdf.line(_RS_MARGIN + 3, bar_top, _RS_MARGIN + 3, bar_bot)

            # Single bars between measures
            for col in range(1, len(chunk)):
                x_bar = _RS_MARGIN + col * CELL_W
                pdf.setLineWidth(0.5)
                pdf.setStrokeColor(_HexColor("#888888"))
                pdf.line(x_bar, bar_top, x_bar, bar_bot)

            # Closing double bar ||
            x_end = _RS_MARGIN + BODY_W
            pdf.setStrokeColor(_HexColor("#444444"))
            pdf.setLineWidth(0.5)
            pdf.line(x_end - 3, bar_top, x_end - 3, bar_bot)
            pdf.setLineWidth(1.5)
            pdf.line(x_end,     bar_top, x_end,     bar_bot)

            # Measure numbers + chord names
            for col, bar in enumerate(chunk):
                x = _RS_MARGIN + col * CELL_W

                # Measure number — tiny, top-left
                pdf.setFillColor(_HexColor("#BBBBBB"))
                pdf.setFont("Helvetica", 6)
                pdf.drawString(x + 6, row_y - 8, str(bar_nums[col]))

                # Chord name — vertically centred, horizontally centred in cell
                chord = bar.get("label") or "N.C."
                fs = 12 if len(chord) <= 5 else (10 if len(chord) <= 8 else (8 if len(chord) <= 13 else 7))
                pdf.setFillColor(_black)
                pdf.setFont("Helvetica-Bold", fs)
                cw = pdf.stringWidth(chord, "Helvetica-Bold", fs)
                if cw > CELL_W - 8:
                    fs = max(6, fs - 1)
                    pdf.setFont("Helvetica-Bold", fs)
                    cw = pdf.stringWidth(chord, "Helvetica-Bold", fs)
                pdf.drawString(x + (CELL_W - cw) / 2, mid_y - fs / 3, chord)

            # Repeat marker — ×N in red, right of closing bar
            if repeat_count > 1:
                pdf.setFillColor(_HexColor("#B71C1C"))
                pdf.setFont("Helvetica-Bold", 9)
                pdf.drawString(_RS_MARGIN + BODY_W + 6, mid_y - 3, f"×{repeat_count}")

            y -= _RS_ROW_H

        y -= 10  # gap after section

    pdf.save()
