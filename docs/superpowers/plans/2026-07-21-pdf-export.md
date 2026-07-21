# Printable PDF Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `--export-pdf` CLI option that renders the already-generated ASCII tab as a paginated, portrait, Courier-font PDF — readable and print-ready, without reimplementing any note/chord placement logic.

**Architecture:** A new `pipeline/pdf_export.py` module reuses `tab_render.render_tab`'s text output (forcing `bars_per_line=2` — the existing default of 4 is too wide to fit an A4 page at 7-8pt Courier), splits it into fixed 8-line blocks (chord row + 6 string rows + separator), computes how many whole blocks fit per page at the chosen font size, and draws paginated pages via `reportlab`'s `Canvas` API (rejected: HTML→PDF, for the same monospace-alignment-integrity reason the original design rejected it). `main.py` gains `--export-pdf`/`--pdf-font-size` flags wired the same way `--export-midi` already is.

**Tech Stack:** Python 3.9, pytest, `reportlab` (new dependency, verified installed as version 5.0.0 in this project's venv).

---

## Context for the engineer

- This plan implements `docs/superpowers/specs/2026-07-21-pdf-export-design.md` in full.
- Working directory for all commands: `guitar_tab_pipeline/` project root.
- Environment gotcha: always invoke tools as `./.venv/bin/python3 -m <tool>` (e.g. `-m pytest`), never a bare script — the venv's console-script wrappers have broken shebangs from an earlier folder rename. (`./.venv/bin/python3` itself is a working symlink to the system interpreter.)
- `reportlab` is already installed in this project's `.venv` (verified: version 5.0.0) — Task 1 just needs to record it in `requirements.txt`, not install anything new.
- Verified font metrics (via `reportlab.pdfbase.pdfmetrics.stringWidth`): Courier is exactly 0.6× the font's point size per character — `stringWidth("0", "Courier", 8) == 4.8`, `stringWidth("0", "Courier", 7) == 4.2`. `reportlab.lib.pagesizes.A4 == (595.2755905511812, 841.8897637795277)`.
- `tab_render.render_tab`'s per-line-group output is ALWAYS exactly 8 lines (1 chord-label row + 6 string rows + 1 blank separator), regardless of how many bars are in that group (1 or 2 when `bars_per_line=2`) — confirmed by reading `tab_render.py`'s loop, which always appends exactly 7 `out.append(...)` calls (chord row + 6 string rows) plus one more `out.append("")` per `for line_start in range(...)` iteration.
- `tab_render.render_tab`'s header is always exactly 8 lines (7 `#`-prefixed comment lines + 1 blank line) before the body starts.

---

### Task 1: Record the `reportlab` dependency

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Add reportlab to requirements.txt**

Add this line to `requirements.txt` (anywhere in the file, e.g. at the end):
```
reportlab>=5.0.0
```

- [ ] **Step 2: Verify it's importable in the project venv**

Run: `./.venv/bin/python3 -c "import reportlab; print(reportlab.Version)"`
Expected: prints `5.0.0` (already installed in this venv from earlier verification — this step just confirms it, no install needed)

- [ ] **Step 3: Commit**

```bash
git add requirements.txt
git commit -m "chore: record reportlab dependency for PDF export"
```

---

### Task 2: Pure pagination-math functions

**Files:**
- Create: `pipeline/pdf_export.py`
- Test: `tests/test_pdf_export.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_pdf_export.py
from pipeline.pdf_export import _blocks_per_page, _split_into_blocks


def test_blocks_per_page_returns_a_positive_count_at_8pt():
    assert _blocks_per_page(8) >= 1


def test_blocks_per_page_returns_a_positive_count_at_7pt():
    assert _blocks_per_page(7) >= 1


def test_blocks_per_page_fits_at_least_as_many_blocks_at_the_smaller_font():
    # Smaller font -> smaller line height -> more lines fit -> at least as
    # many whole 8-line blocks fit per page.
    assert _blocks_per_page(7) >= _blocks_per_page(8)


def test_split_into_blocks_groups_lines_into_chunks_of_eight():
    lines = [f"line{i}" for i in range(16)]
    blocks = _split_into_blocks(lines)
    assert len(blocks) == 2
    assert blocks[0] == lines[:8]
    assert blocks[1] == lines[8:]


def test_split_into_blocks_handles_empty_input():
    assert _split_into_blocks([]) == []
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `./.venv/bin/python3 -m pytest tests/test_pdf_export.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline.pdf_export'`

- [ ] **Step 3: Write the implementation**

```python
# pipeline/pdf_export.py
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
```

(The `export_pdf` function that uses these, plus the `canvas`/`ChordSegment`/`FrettedNote`/`KeyEstimate`/`Tuning` imports, is added in Task 3 — this task only adds the pure pagination-math pieces and the module docstring. The unused-import warnings this creates temporarily, if any linter is run, are expected and resolved by Task 3.)

- [ ] **Step 4: Run the tests to verify they pass**

Run: `./.venv/bin/python3 -m pytest tests/test_pdf_export.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add pipeline/pdf_export.py tests/test_pdf_export.py
git commit -m "feat: add PDF pagination math (blocks-per-page, line grouping)"
```

---

### Task 3: `export_pdf` orchestration

**Files:**
- Modify: `pipeline/pdf_export.py`

- [ ] **Step 1: Append `export_pdf` to `pipeline/pdf_export.py`**

```python
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
```

- [ ] **Step 2: Manually verify with a synthetic call (no real audio needed)**

Run:
```bash
./.venv/bin/python3 -c "
from pathlib import Path
from pipeline.chord_detection import ChordSegment
from pipeline.fretboard import FrettedNote
from pipeline.key_detection import KeyEstimate
from pipeline.pdf_export import export_pdf
from pipeline.tuning import STANDARD_E_A_D_G_B_E, find_tuning

bars = [ChordSegment(bar_index=i, start=float(i*2), end=float(i*2+2), label='Em') for i in range(20)]
notes = [FrettedNote(string=0, fret=0, start=0.0, end=0.5, pitch=40)]
key = KeyEstimate(tonic='E', mode='minor', correlation=0.9)
tuning = find_tuning(STANDARD_E_A_D_G_B_E)

export_pdf(Path('/tmp/pdf_export_smoke_test.pdf'), bars, notes, key, 120.0, 'smoke_test.wav', tuning, font_size=8)
print('OK, file exists:', Path('/tmp/pdf_export_smoke_test.pdf').exists())
print('file size:', Path('/tmp/pdf_export_smoke_test.pdf').stat().st_size, 'bytes')
"
```
Expected: prints `OK, file exists: True` and a non-trivial file size (at least a few KB). This is a synthetic-data smoke check (20 fake bars, one fake note) — not a real song, but enough to confirm `export_pdf` runs end-to-end without crashing and produces a real PDF file. Full visual verification with a real song's output happens in the optional Task 5.

Run: `./.venv/bin/python3 -m pytest tests/test_pdf_export.py -v`
Expected: still 5 passed (this task didn't touch the pagination-math functions, just added a new function alongside them)

- [ ] **Step 3: Commit**

```bash
git add pipeline/pdf_export.py
git commit -m "feat: render paginated PDF tab via reportlab Canvas"
```

## Context for Task 3's reviewer

`export_pdf` has no dedicated pytest unit test — like `separation.separate`/`transcription.transcribe`, its meaningful verification is "does the rendered PDF look right," which a fast unit test can't check; the manual smoke test above (and the optional Task 5 smoke test on real audio) are the appropriate verification level, consistent with this codebase's existing precedent.

---

### Task 4: Wire `--export-pdf`/`--pdf-font-size` into `main.py`

**Files:**
- Modify: `main.py`

- [ ] **Step 1: Add `pdf_export` to the pipeline import line**

Change:
```python
from pipeline import chord_detection, fretboard, key_detection, midi_export, separation, tab_render, transcription, tuning, voice_split
```
to:
```python
from pipeline import chord_detection, fretboard, key_detection, midi_export, pdf_export, separation, tab_render, transcription, tuning, voice_split
```

- [ ] **Step 2: Add the two new CLI arguments**

In `parse_args()`, right after the existing `--export-midi` argument, add:
```python
    parser.add_argument("--export-pdf", action="store_true",
                         help="Also export a printable PDF (Courier, portrait, "
                              "paginated) of the main tab")
    parser.add_argument("--pdf-font-size", type=int, default=8, choices=[7, 8],
                         help="Font size for --export-pdf output (default: %(default)s)")
```

- [ ] **Step 3: Refactor the voice-split labels into named variables, and add PDF export for both voices**

Change:
```python
        if args.voices == 2:
            treble_notes, bass_notes = voice_split.split_voices(fretted_notes)
            treble_path = output_path.with_name(f"{output_path.stem}_guitare_aigue.txt")
            bass_path = output_path.with_name(f"{output_path.stem}_guitare_grave.txt")
            treble_strings = "/".join(selected_tuning.string_names[3:])
            bass_strings = "/".join(selected_tuning.string_names[:3])
            tab_render.write_tab(treble_path, chords, treble_notes, key_estimate, tempo,
                                  f"{audio_path.name} (voix aigue {treble_strings} -- heuristique, pas une vraie 2e guitare)",
                                  tuning=selected_tuning)
            tab_render.write_tab(bass_path, chords, bass_notes, key_estimate, tempo,
                                  f"{audio_path.name} (voix grave {bass_strings} -- heuristique, pas une vraie 2e guitare)",
                                  tuning=selected_tuning)
            print(f"Voice split: {treble_path}, {bass_path}")
```
to:
```python
        if args.voices == 2:
            treble_notes, bass_notes = voice_split.split_voices(fretted_notes)
            treble_path = output_path.with_name(f"{output_path.stem}_guitare_aigue.txt")
            bass_path = output_path.with_name(f"{output_path.stem}_guitare_grave.txt")
            treble_strings = "/".join(selected_tuning.string_names[3:])
            bass_strings = "/".join(selected_tuning.string_names[:3])
            treble_label = f"{audio_path.name} (voix aigue {treble_strings} -- heuristique, pas une vraie 2e guitare)"
            bass_label = f"{audio_path.name} (voix grave {bass_strings} -- heuristique, pas une vraie 2e guitare)"
            tab_render.write_tab(treble_path, chords, treble_notes, key_estimate, tempo,
                                  treble_label, tuning=selected_tuning)
            tab_render.write_tab(bass_path, chords, bass_notes, key_estimate, tempo,
                                  bass_label, tuning=selected_tuning)
            print(f"Voice split: {treble_path}, {bass_path}")

            if args.export_pdf:
                treble_pdf_path = output_path.with_name(f"{output_path.stem}_guitare_aigue.pdf")
                bass_pdf_path = output_path.with_name(f"{output_path.stem}_guitare_grave.pdf")
                pdf_export.export_pdf(treble_pdf_path, chords, treble_notes, key_estimate, tempo,
                                       treble_label, selected_tuning, font_size=args.pdf_font_size)
                pdf_export.export_pdf(bass_pdf_path, chords, bass_notes, key_estimate, tempo,
                                       bass_label, selected_tuning, font_size=args.pdf_font_size)
                print(f"Voice split PDF: {treble_pdf_path}, {bass_pdf_path}")
```

(This extracts `treble_label`/`bass_label` into named variables so the same label text can be passed to both `tab_render.write_tab` and `pdf_export.export_pdf` without duplicating the f-string — the only reason for this small refactor is that Task 4 needs that label text a second time; nothing else about the block's behavior changes.)

- [ ] **Step 4: Add PDF export for the main tab**

Change:
```python
        if args.export_midi:
            midi_path = output_path.with_suffix(".mid")
            midi_export.export_midi(midi_path, fretted_notes, tempo)
            print(f"MIDI export: {midi_path}")

        print(f"\nDone. Tab written to: {output_path}")
```
to:
```python
        if args.export_midi:
            midi_path = output_path.with_suffix(".mid")
            midi_export.export_midi(midi_path, fretted_notes, tempo)
            print(f"MIDI export: {midi_path}")

        if args.export_pdf:
            pdf_path = output_path.with_suffix(".pdf")
            pdf_export.export_pdf(pdf_path, chords, fretted_notes, key_estimate, tempo,
                                   audio_path.name, selected_tuning, font_size=args.pdf_font_size)
            print(f"PDF export: {pdf_path}")

        print(f"\nDone. Tab written to: {output_path}")
```

- [ ] **Step 5: Run the full test suite**

Run: `./.venv/bin/python3 -m pytest -v`
Expected: all tests pass (5 in `tests/test_pdf_export.py` from Task 2, plus all pre-existing tests — 41 total)

- [ ] **Step 6: Verify syntax and `--help`**

Run: `./.venv/bin/python3 -c "import ast; ast.parse(open('main.py').read())"`
Expected: no output (valid syntax)

Run: `./.venv/bin/python3 main.py --help`
Expected: output includes `--export-pdf` and `--pdf-font-size {7,8}` among the listed options

- [ ] **Step 7: Commit**

```bash
git add main.py
git commit -m "feat: wire --export-pdf/--pdf-font-size into the CLI"
```

---

### Task 5 (optional manual smoke test): Full pipeline run on real audio with `--export-pdf`

Not part of the automated test suite — re-runs the full, slow (Demucs + basic-pitch) pipeline on a real song to confirm the PDF actually looks right (correct font, portrait orientation, readable, no cut-off lines) — something no unit test can check. Skip if time-constrained; Tasks 1-4's automated tests and manual synthetic-data check already cover the new logic.

- [ ] **Step 1: Re-run the pipeline on a song already used with this project**

Run (adjust the input path to any available song):
```bash
cd "/Users/joao.silva/Library/CloudStorage/GoogleDrive-davisthe8th@gmail.com/My Drive/GARAGEBAND/VALLETOFNOONE/guitar_tab_pipeline"
./.venv/bin/python3 main.py "<path/to/a/song>" --export-pdf --pdf-font-size 8 --output /tmp/pdf_smoke_test_tab.txt
```
Expected: completes through all 7 steps and additionally prints `PDF export: /tmp/pdf_smoke_test_tab.pdf`.

- [ ] **Step 2: Open the PDF and inspect it**

Run: `open /tmp/pdf_smoke_test_tab.pdf` (macOS — opens in the default PDF viewer)
Expected (visual, no automated check): portrait A4 pages, Courier font, a page header showing the song name/key/tempo/tuning/page number on every page, no line running off the right edge of the page, and a "readable" font size — matching the original ask ("lisible, taille 7 ou 8pt").
