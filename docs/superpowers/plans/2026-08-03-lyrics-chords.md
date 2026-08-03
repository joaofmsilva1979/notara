# Lyrics + Chords Feature Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an optional lyrics input that uses stable-whisper forced alignment on the Demucs vocal stem to produce a chord chart with chord names positioned above the correct words, displayed as a new "Lyrics" tab in the results.

**Architecture:** New `pipeline/lyrics_align.py` handles all alignment and formatting. API routes accept optional lyrics via file upload or pasted text. Worker calls `align_lyrics` after chord detection when lyrics are present. Frontend adds a collapsible lyrics section to the upload panel and renders a "Lyrics" tab alongside existing instrument tabs.

**Tech Stack:** `stable-whisper>=2.7.0`, `python-docx>=1.1.0`, `reportlab` (existing), FastAPI (existing).

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `pipeline/lyrics_align.py` | Create | Parse lyrics, call stable-whisper, map chords to words, format chord chart |
| `pipeline/pdf_export.py` | Modify | Add `export_lyrics_pdf()` |
| `tests/test_lyrics_align.py` | Create | Unit tests for helpers and `align_lyrics` |
| `api/requirements.txt` | Modify | Add `stable-whisper>=2.7.0`, `python-docx>=1.1.0` |
| `api/routes.py` | Modify | Accept `lyrics_file`/`lyrics_text`; support `lyrics` in download route |
| `api/worker.py` | Modify | Call `align_lyrics` after chord detection; write `lyrics.txt` + `lyrics.pdf` |
| `index.html` | Modify | Add collapsible lyrics section below audio drop zone |
| `css/main.css` | Modify | Style lyrics section, chord lines (red), section labels |
| `js/app.js` | Modify | Wire lyrics UI; render "Lyrics" tab; transpose chord lines |

---

### Task 1: `pipeline/lyrics_align.py` — core alignment module

**Files:**
- Create: `pipeline/lyrics_align.py`
- Create: `tests/test_lyrics_align.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_lyrics_align.py
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
    # Two chords at positions 0 and 1 — gap must be at least 2 chars after "Am"
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
    # Midpoint of 11-char string → position 5
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd "/Users/joao.silva/Library/CloudStorage/GoogleDrive-davisthe8th@gmail.com/My Drive/GARAGEBAND/VALLETOFNOONE/guitar_tab_pipeline"
python -m pytest tests/test_lyrics_align.py -v 2>&1 | head -20
```

Expected: FAIL — `ModuleNotFoundError: No module named 'pipeline.lyrics_align'`

- [ ] **Step 3: Create `pipeline/lyrics_align.py`**

```python
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
    return int(frac * len(line))


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
        t_end = words[end_idx][2]
        word_idx = end_idx + 1
        result.append((line, t_start, t_end))

    return result


def align_lyrics(
    lyrics_text: str,
    vocal_stem_path: Path,
    chord_events: list,  # List[ChordSegment] with .start (float) and .label (str)
) -> str:
    """Return a formatted chord chart string, or empty string on failure.

    On ImportError (stable_whisper not installed): returns "".
    On missing vocal stem: returns "".
    On alignment failure: returns plain lyrics without chord positions.
    """
    lyrics_text = lyrics_text.strip()
    if not lyrics_text:
        return ""
    if not _HAS_STABLE_WHISPER:
        return ""
    if not vocal_stem_path.exists():
        return ""

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
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/test_lyrics_align.py -v
```

Expected: All 9 tests pass.

- [ ] **Step 5: Commit**

```bash
git add pipeline/lyrics_align.py tests/test_lyrics_align.py
git commit -m "feat: add lyrics_align module with stable-whisper forced alignment"
```

---

### Task 2: PDF export for lyrics

**Files:**
- Modify: `pipeline/pdf_export.py`
- Modify: `tests/test_pdf_export.py`

- [ ] **Step 1: Write the failing test**

Open `tests/test_pdf_export.py` and append this test at the bottom:

```python
def test_export_lyrics_pdf(tmp_path):
    from pipeline.pdf_export import export_lyrics_pdf
    chart = "[Verse 1]\n  Am      G\nHello world\n"
    path = tmp_path / "lyrics.pdf"
    export_lyrics_pdf(path, chart)
    assert path.exists()
    assert path.stat().st_size > 200
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_pdf_export.py::test_export_lyrics_pdf -v
```

Expected: FAIL — `ImportError: cannot import name 'export_lyrics_pdf'`

- [ ] **Step 3: Add imports and `export_lyrics_pdf` to `pipeline/pdf_export.py`**

Add these two lines at the top of the file, after the existing `import` block (after line 10 `from .tuning import Tuning`):

```python
import re as _re
from reportlab.lib.colors import HexColor as _HexColor
```

Then append these definitions at the very end of `pipeline/pdf_export.py`:

```python
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
```

- [ ] **Step 4: Run test**

```bash
python -m pytest tests/test_pdf_export.py::test_export_lyrics_pdf -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add pipeline/pdf_export.py tests/test_pdf_export.py
git commit -m "feat: add export_lyrics_pdf to pdf_export"
```

---

### Task 3: API — requirements + routes

**Files:**
- Modify: `api/requirements.txt`
- Modify: `api/routes.py`

- [ ] **Step 1: Add dependencies to `api/requirements.txt`**

Append two lines at the end of `api/requirements.txt`:

```
stable-whisper>=2.7.0
python-docx>=1.1.0
```

- [ ] **Step 2: Write failing test for the route changes**

Open `tests/test_api_routes.py` and append:

```python
def test_create_job_with_lyrics_text(client, tmp_audio):
    resp = client.post("/api/jobs", data={
        "lyrics_text": "[Verse 1]\nHello world",
    }, files={"file": ("test.mp3", tmp_audio, "audio/mpeg")})
    assert resp.status_code == 200
    assert "job_id" in resp.json()


def test_download_lyrics_txt_not_found(client, done_job_id):
    resp = client.get(f"/api/jobs/{done_job_id}/download/lyrics/txt")
    # 404 because lyrics.txt wasn't written (no lyrics submitted)
    assert resp.status_code == 404


def test_download_lyrics_invalid_fmt(client, done_job_id):
    resp = client.get(f"/api/jobs/{done_job_id}/download/lyrics/midi")
    assert resp.status_code == 400
```

- [ ] **Step 3: Run to verify the tests fail or behave unexpectedly**

```bash
python -m pytest tests/test_api_routes.py::test_create_job_with_lyrics_text tests/test_api_routes.py::test_download_lyrics_txt_not_found tests/test_api_routes.py::test_download_lyrics_invalid_fmt -v 2>&1 | tail -20
```

Expected: `test_create_job_with_lyrics_text` → 422 (field unknown); download tests → 400 (invalid track).

- [ ] **Step 4: Update `api/routes.py`**

**4a.** In the `create_job` function signature, add two optional parameters after `keys_tab`:

```python
    lyrics_file: Optional[UploadFile] = File(None),
    lyrics_text: Optional[str] = Form(""),
```

**4b.** After the existing `params = { ... }` dict (after `"keys_tab": keys_tab,`), add lyrics resolution logic before `background_tasks.add_task(...)`:

```python
    # Resolve lyrics: file takes priority over pasted text
    lyrics_raw: Optional[str] = None
    if lyrics_file and lyrics_file.filename:
        suffix = Path(lyrics_file.filename).suffix.lower()
        raw_bytes = await lyrics_file.read()
        if suffix == ".docx":
            try:
                from docx import Document
                import io as _io
                doc = Document(_io.BytesIO(raw_bytes))
                lyrics_raw = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
            except Exception:
                lyrics_raw = None
        else:
            try:
                lyrics_raw = raw_bytes.decode("utf-8", errors="replace")
            except Exception:
                lyrics_raw = None
    elif lyrics_text and lyrics_text.strip():
        lyrics_raw = lyrics_text.strip()

    params["lyrics_raw"] = lyrics_raw
```

**4c.** In `download_file`, update `allowed_tracks` and add the lyrics guard:

```python
    allowed_tracks = {"guitar1", "guitar2", "bass", "vocals", "keys", "drums", "lyrics"}
    allowed_fmts = {"pdf", "txt", "midi"}
    if track not in allowed_tracks or fmt not in allowed_fmts:
        raise HTTPException(400, "Invalid track or format")
    if track == "drums" and fmt not in {"txt"}:
        raise HTTPException(400, "Drums only supports txt format")
    if track == "lyrics" and fmt not in {"txt", "pdf"}:
        raise HTTPException(400, "Lyrics supports txt and pdf formats only")
```

- [ ] **Step 5: Run tests**

```bash
python -m pytest tests/test_api_routes.py::test_create_job_with_lyrics_text tests/test_api_routes.py::test_download_lyrics_txt_not_found tests/test_api_routes.py::test_download_lyrics_invalid_fmt -v
```

Expected: All 3 pass.

- [ ] **Step 6: Commit**

```bash
git add api/requirements.txt api/routes.py tests/test_api_routes.py
git commit -m "feat: api accepts optional lyrics_file/lyrics_text, supports lyrics download"
```

---

### Task 4: Worker — call `align_lyrics`

**Files:**
- Modify: `api/worker.py`

- [ ] **Step 1: Add import at top of `api/worker.py`**

After the existing pipeline imports (after `from pipeline.pdf_export import export_pdf`), add:

```python
from pipeline.lyrics_align import align_lyrics as _align_lyrics
from pipeline.pdf_export import export_lyrics_pdf as _export_lyrics_pdf
```

- [ ] **Step 2: Update `_count_steps` to account for lyrics**

In the `_count_steps` function, after `if params["keys_tab"]: base += 1`, add:

```python
    if params.get("lyrics_raw"):
        base += 1
```

- [ ] **Step 3: Add lyrics step in `run_job`**

After the keys block (after `results["tabs"]["keys"] = keys_result["text"]`), and before `job.results = results`, add:

```python
        # Optional: Lyrics chord chart
        if params.get("lyrics_raw"):
            step += 1
            _step(job, step, "Aligning lyrics to audio")
            stem_dir = work_dir / "stems" / DEMUCS_MODEL / audio_path.stem
            vocal_path = stem_dir / "vocals.wav"
            lyrics_chart = _align_lyrics(
                params["lyrics_raw"],
                vocal_path,
                bars,  # List[ChordSegment] — .start and .label used
            )
            if lyrics_chart:
                (work_dir / "lyrics.txt").write_text(lyrics_chart, encoding="utf-8")
                _export_lyrics_pdf(work_dir / "lyrics.pdf", lyrics_chart)
                results["tabs"]["lyrics"] = lyrics_chart
```

- [ ] **Step 4: Verify worker imports cleanly**

```bash
cd "/Users/joao.silva/Library/CloudStorage/GoogleDrive-davisthe8th@gmail.com/My Drive/GARAGEBAND/VALLETOFNOONE/guitar_tab_pipeline"
python -c "from api.worker import run_job; print('OK')"
```

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add api/worker.py
git commit -m "feat: worker calls align_lyrics when lyrics provided, writes lyrics.txt + lyrics.pdf"
```

---

### Task 5: Frontend HTML + CSS

**Files:**
- Modify: `index.html`
- Modify: `css/main.css`

- [ ] **Step 1: Add lyrics section HTML to `index.html`**

Find the drop zone in `index.html` — the line containing `<div id="drop-zone"` (inside `.upload-area`). Insert the following block **after** the closing `</div>` of the drop zone section and **before** the options grid (`<div class="options-grid"` or similar):

```html
<!-- Lyrics (optional) -->
<div id="lyrics-section" class="lyrics-section">
  <button id="lyrics-toggle" class="lyrics-toggle" type="button">+ ADD LYRICS <span class="lyrics-toggle-hint">optional</span></button>
  <div id="lyrics-body" class="lyrics-body" style="display:none">
    <div id="lyrics-drop" class="lyrics-drop">
      <span>Drop .txt / .doc / .docx or <button id="lyrics-browse" class="btn-link" type="button">browse</button></span>
      <input type="file" id="lyrics-file-input" accept=".txt,.doc,.docx" style="display:none">
      <div id="lyrics-file-indicator" class="lyrics-file-indicator" style="display:none"></div>
    </div>
    <div class="lyrics-or">— or —</div>
    <textarea id="lyrics-textarea" class="lyrics-textarea" placeholder="Paste lyrics here..." rows="6"></textarea>
  </div>
</div>
```

- [ ] **Step 2: Add CSS to `css/main.css`**

Append the following at the end of `css/main.css`:

```css
/* ── Lyrics section ─────────────────────────────────────────── */
.lyrics-section {
  margin-top: 10px;
}

.lyrics-toggle {
  width: 100%;
  background: none;
  border: 1px solid rgba(255,255,255,0.15);
  border-radius: 6px;
  color: #ccc;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: .08em;
  padding: 8px 12px;
  text-align: left;
  cursor: pointer;
  transition: border-color .2s, color .2s;
}

.lyrics-toggle:hover {
  border-color: #B71C1C;
  color: #fff;
}

.lyrics-toggle-hint {
  font-weight: 400;
  color: #888;
  margin-left: 6px;
  font-size: 10px;
}

.lyrics-body {
  margin-top: 8px;
  padding: 10px;
  border-left: 2px solid #B71C1C;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.lyrics-drop {
  border: 1px dashed rgba(255,255,255,0.2);
  border-radius: 6px;
  padding: 10px 12px;
  font-size: 11px;
  color: #aaa;
  text-align: center;
}

.lyrics-drop .btn-link {
  background: none;
  border: none;
  color: #B71C1C;
  cursor: pointer;
  font-size: 11px;
  padding: 0;
  text-decoration: underline;
}

.lyrics-file-indicator {
  margin-top: 4px;
  font-size: 10px;
  color: #aaa;
}

.lyrics-or {
  text-align: center;
  font-size: 10px;
  color: #666;
}

.lyrics-textarea {
  width: 100%;
  box-sizing: border-box;
  background: #1a1a1a;
  border: 1px solid rgba(255,255,255,0.12);
  border-radius: 6px;
  color: #ddd;
  font-family: "Courier New", monospace;
  font-size: 11px;
  line-height: 1.5;
  padding: 8px;
  resize: vertical;
}

.lyrics-textarea:focus {
  outline: none;
  border-color: #B71C1C;
}

/* ── Lyrics tab content ─────────────────────────────────────── */
.tab-chord-line {
  display: block;
  color: #B71C1C;
  font-weight: 600;
  white-space: pre;
}

.tab-lyric-line {
  display: block;
  color: #e8e8e8;
  white-space: pre;
}
```

- [ ] **Step 3: Verify HTML is well-formed**

Open `index.html` in a browser locally (`python3 -m http.server 3000`) and check the lyrics toggle button appears below the audio upload area.

- [ ] **Step 4: Commit**

```bash
git add index.html css/main.css
git commit -m "feat: add lyrics section UI and chord/lyric line styles"
```

---

### Task 6: Frontend JavaScript — wire UI and render tab

**Files:**
- Modify: `js/app.js`

- [ ] **Step 1: Add state variables**

At the top of `js/app.js`, after `let pwaInstallPrompt = null;`, add:

```javascript
let selectedLyricsFile = null;
```

- [ ] **Step 2: Add DOM refs**

After the existing DOM refs block, add:

```javascript
const lyricsToggle    = document.getElementById('lyrics-toggle');
const lyricsBody      = document.getElementById('lyrics-body');
const lyricsDrop      = document.getElementById('lyrics-drop');
const lyricsFileInput = document.getElementById('lyrics-file-input');
const lyricsBrowse    = document.getElementById('lyrics-browse');
const lyricsIndicator = document.getElementById('lyrics-file-indicator');
const lyricsTextarea  = document.getElementById('lyrics-textarea');
```

- [ ] **Step 3: Wire lyrics toggle and file input**

After the `_setupToggle` calls, add:

```javascript
// ── Lyrics section ────────────────────────────────────────────
lyricsToggle.addEventListener('click', () => {
  const open = lyricsBody.style.display !== 'none';
  lyricsBody.style.display = open ? 'none' : 'flex';
  lyricsToggle.textContent = open
    ? '+ ADD LYRICS '
    : '− REMOVE LYRICS ';
  const hint = document.createElement('span');
  hint.className = 'lyrics-toggle-hint';
  hint.textContent = 'optional';
  lyricsToggle.appendChild(hint);
});

lyricsBrowse.addEventListener('click', () => lyricsFileInput.click());

lyricsFileInput.addEventListener('change', () => {
  if (lyricsFileInput.files[0]) _setLyricsFile(lyricsFileInput.files[0]);
});

lyricsDrop.addEventListener('dragover', e => { e.preventDefault(); lyricsDrop.classList.add('drag-over'); });
lyricsDrop.addEventListener('dragleave', () => lyricsDrop.classList.remove('drag-over'));
lyricsDrop.addEventListener('drop', e => {
  e.preventDefault();
  lyricsDrop.classList.remove('drag-over');
  if (e.dataTransfer.files[0]) _setLyricsFile(e.dataTransfer.files[0]);
});

function _setLyricsFile(file) {
  selectedLyricsFile = file;
  lyricsIndicator.textContent = `Selected: ${file.name}`;
  lyricsIndicator.style.display = 'block';
  lyricsTextarea.value = '';
}
```

- [ ] **Step 4: Include lyrics in FormData on submit**

In `_submitJob`, after the existing `formData.append('keys_tab', ...)` line, add:

```javascript
  if (selectedLyricsFile) {
    formData.append('lyrics_file', selectedLyricsFile);
  } else if (lyricsTextarea.value.trim()) {
    formData.append('lyrics_text', lyricsTextarea.value.trim());
  }
```

- [ ] **Step 5: Add `isChordLine` helper and update `_tabLabel`**

Add after the `_tabLabel` function:

```javascript
function _isChordAnnotationLine(line) {
  const s = line.trim();
  return s.length > 0 && !/[a-z]/.test(s);
}
```

Update `_tabLabel` to include lyrics:

```javascript
function _tabLabel(track) {
  return { guitar1: 'Guitar 1', guitar2: 'Guitar 2', bass: 'Bass', vocals: 'Vocals', drums: 'Drums', keys: 'Keys', lyrics: 'Lyrics' }[track] || track;
}
```

- [ ] **Step 6: Add lyrics rendering in `_renderTab`**

In the `_renderTab` function, add a lyrics case **before** the `const segments = text.split('\n\n');` line:

```javascript
  if (track === 'lyrics') {
    tabContent.innerHTML = '';
    const lines = text.split('\n');
    lines.forEach(line => {
      const span = document.createElement('span');
      const stripped = line.trim();
      if (stripped.startsWith('[') && stripped.endsWith(']')) {
        span.className = 'tab-comment';
      } else if (_isChordAnnotationLine(line)) {
        span.className = 'tab-chord-line';
        span.dataset.origChordLine = line;
      } else {
        span.className = 'tab-lyric-line';
      }
      span.textContent = line;
      tabContent.appendChild(span);
      tabContent.appendChild(document.createTextNode('\n'));
    });
    tabDownloads.innerHTML = '';
    tabDownloads.appendChild(_dlBtn('↓ TXT', 'dl-txt', 'lyrics', 'txt'));
    tabDownloads.appendChild(_dlBtn('↓ PDF', 'dl-pdf', 'lyrics', 'pdf'));
    return;
  }
```

- [ ] **Step 7: Handle transpose on lyrics chord lines**

In `playback.js`, find `_applyTranspose()`. After the existing block that processes `.tab-bar` spans, add:

```javascript
  // Transpose chord annotation lines in lyrics tab
  document.querySelectorAll('.tab-chord-line').forEach(span => {
    const orig = span.dataset.origChordLine || span.textContent;
    span.dataset.origChordLine = orig;
    span.textContent = orig.replace(
      /\b([A-G][#b]?(?:m(?:aj7?|7b5)?|7|maj7|sus[24]|dim7?|aug)?)\b/g,
      name => _transposeChordName(name, _transposeSteps)
    );
  });
```

- [ ] **Step 8: Reset lyrics state on new job**

In `_submitJob`, after `resultsData = null;`, add:

```javascript
  selectedLyricsFile = null;
```

- [ ] **Step 9: Commit**

```bash
git add js/app.js
git commit -m "feat: wire lyrics UI, render Lyrics tab, transpose chord annotation lines"
```

---

## Final Verification

- [ ] Start the server: `python3 -m uvicorn api.main:app --reload`
- [ ] Start the frontend: `python3 -m http.server 3000`
- [ ] Upload a short song (1–2 min) with a `.txt` lyrics file
- [ ] Verify: job completes, "Lyrics" tab appears, chord names are above words
- [ ] Verify: ↓ TXT and ↓ PDF download correctly
- [ ] Verify: Transpose buttons shift chord names on the Lyrics tab
- [ ] Verify: a job without lyrics produces no "Lyrics" tab
- [ ] Run full test suite: `python -m pytest -v`
