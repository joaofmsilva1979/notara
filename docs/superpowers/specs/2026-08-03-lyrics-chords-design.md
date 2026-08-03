# Lyrics + Chords Feature — Design Spec

**Goal:** Accept an optional lyrics file (or pasted text) alongside audio; perform forced alignment to produce a chord chart in Ultimate Guitar format with chord names positioned above the correct words.

**Architecture:** New `pipeline/lyrics_align.py` module using `stable-whisper` on the Demucs vocal stem. Self-contained — no changes to existing pipeline modules. Results surface as a new `lyrics` tab in the job results.

**Tech Stack:** `stable-whisper`, `openai-whisper` (model: `small`), `python-docx` (for .docx parsing), `reportlab` (PDF, already in use).

---

## 1. Input

- Submitted at job creation time alongside the audio file.
- Two mutually exclusive inputs — file takes priority if both provided:
  - `lyrics_file`: multipart upload, accepts `.txt` and `.docx`
  - `lyrics_text`: form field string (paste)
- Lyrics are optional. If absent, job proceeds exactly as today.
- Section markers (`[Verse 1]`, `[Chorus]`, `[Bridge]`, etc.) are supported — any line matching `^\[.+\]$` is treated as a section label.

## 2. Processing Pipeline

Order within the existing job worker:

1. Demucs separation (existing) → vocal stem at `{job_dir}/vocals.wav`
2. Chord detection (existing) → `chord_events: List[ChordEvent]` with `.time` and `.name`
3. **[NEW]** `align_lyrics(lyrics_text, vocal_stem_path, chord_events)` → chord chart string
4. Store as `results["tabs"]["lyrics"]`

`align_lyrics` is only called when lyrics text is non-empty after stripping.

## 3. `pipeline/lyrics_align.py`

### Public interface

```python
def align_lyrics(
    lyrics_text: str,
    vocal_stem_path: Path,
    chord_events: list,   # list of objects with .time (float) and .name (str)
) -> str:
    """Return a formatted chord chart string, or empty string on failure."""
```

### Internal steps

1. **Parse lyrics** — split into lines; detect section labels (regex `^\[.+\]$`).
2. **Forced alignment** — load `stable_whisper.load_model("small")`; call `model.align(str(vocal_stem_path), lyrics_text, language="en")`; extract per-word timestamps as `[(word, start_sec, end_sec), ...]`.
3. **Group words into lines** — reconstruct lyric lines from word list, tracking each line's `t_start` (first word start) and `t_end` (last word end).
4. **Map chords to lines** — for each lyric line, collect all chord events where `t_start <= chord.time < t_end`.
5. **Build chord line** — for each chord in the line, find the character position of the word being sung at `chord.time`; insert chord name at that position; enforce minimum 2-char gap between chord names.
6. **Format output** — assemble final string: section labels on their own line (no chord line above them), chord line + lyric line pairs for content lines, `— instrumental —` for bars with no matched lyrics.

### Failure handling

- If `stable_whisper` is not installed → return `""` (lyrics tab silently omitted).
- If alignment produces no word timestamps → return plain lyrics with no chord positions (chords listed at top as a fallback header).
- If vocal stem missing → return `""`.

## 4. API Changes

### `api/routes.py` — POST /jobs

Add optional fields:
```python
lyrics_file: Optional[UploadFile] = File(None)
lyrics_text: Optional[str] = Form("")
```

Resolution order:
1. If `lyrics_file` provided and non-empty → read bytes, decode as UTF-8 (`.txt`) or extract text via `python-docx` (`.docx`).
2. Else if `lyrics_text` provided and non-empty → use as-is.
3. Else → `lyrics_raw = None`.

Pass `lyrics_raw` to the job worker.

### `api/routes.py` — GET /download/{track}/{fmt}

Add `track == "lyrics"` support:
- `fmt = "txt"` → return chord chart string as `text/plain`
- `fmt = "pdf"` → render chord chart to PDF via `pipeline/pdf_export.py` (monospace layout, A4, Courier New 9pt, section labels bold)

## 5. Frontend

### `index.html`

Below the existing drop zone, before the options grid:

```html
<div id="lyrics-section">
  <button id="lyrics-toggle" class="lyrics-toggle">+ ADD LYRICS</button>
  <div id="lyrics-body" class="lyrics-body" style="display:none">
    <div id="lyrics-drop" class="lyrics-drop">
      <span>Drop .txt / .doc / .docx or <button id="lyrics-browse">browse</button></span>
      <input type="file" id="lyrics-file-input" accept=".txt,.doc,.docx" style="display:none">
      <div id="lyrics-file-indicator" style="display:none"></div>
    </div>
    <div class="lyrics-or">or</div>
    <textarea id="lyrics-textarea" placeholder="Paste lyrics here..." rows="6"></textarea>
  </div>
</div>
```

### `js/app.js`

- Wire `lyrics-toggle` to show/hide `lyrics-body`.
- Wire `lyrics-browse` → `lyrics-file-input.click()`.
- File drag-and-drop on `lyrics-drop`.
- On submit: append `lyrics_file` (if file selected) or `lyrics_text` (if textarea non-empty) to FormData. File takes priority.
- `_renderTab("lyrics", data)`: render chord chart in monospace pre block; section labels get class `tab-comment`; chord lines get class `tab-chord-line`; lyric lines get class `tab-lyric-line`.
- Download buttons: `↓ TXT` and `↓ PDF` (same `_dlBtn` pattern, track=`"lyrics"`).
- Transpose: `_applyTranspose()` already operates on `.tab-bar` spans — lyrics tab chord lines need separate handling: chord names in `.tab-chord-line` spans shift via `_transposeChordName()`.

### `css/main.css`

New rules:
- `.lyrics-toggle` — styled like a secondary button, full width, left-aligned text
- `.lyrics-body` — padding, border-left accent
- `.lyrics-drop` — same visual as main drop zone but smaller
- `.lyrics-or` — centered divider
- `#lyrics-textarea` — monospace font, full width, dark bg matching theme
- `.tab-chord-line` — color: `#B71C1C` (red), font-weight 600, letter-spacing matches lyric line
- `.tab-lyric-line` — normal weight

## 6. Chord Chart Text Format

```
[Verse 1]
    Dm             Bb                  Gm
The glass is not half full, it's not half empty
    Dm              Bb                Gm
Instead it lays half fucked up on the floor

— instrumental —

[Chorus]
    C                    G
We'll take nothing with us when we leave
```

Rules:
- Section labels: no chord line above them.
- Blank line between sections.
- `— instrumental —` for bars with no matched lyric line.
- Chord names positioned at character offset of the word being sung when chord changes.
- Minimum 2-character gap enforced between adjacent chord names by padding.

## 7. Export

- **TXT**: raw chord chart string, UTF-8, `Content-Disposition: attachment; filename="lyrics-chords.txt"`
- **PDF**: A4, Courier New 9pt, 25mm margins, section labels bold 10pt, chord lines in `#B71C1C`, lyric lines normal weight. Uses existing `reportlab` pipeline.

## 8. Dependencies

Add to `api/requirements.txt`:
- `stable-whisper>=2.7.0`
- `python-docx>=1.1.0`

`openai-whisper` is pulled in as a dependency of `stable-whisper`.

## 9. Testing

- `tests/test_lyrics_align.py`:
  - `test_parse_section_labels` — lines matching `^\[.+\]$` identified correctly
  - `test_chord_line_no_overlap` — two chords <2 chars apart get padded to minimum gap
  - `test_align_lyrics_no_stable_whisper` — graceful fallback when library absent (mock ImportError)
  - `test_align_lyrics_empty_input` — returns `""` without crashing
- Manual test: upload a 3-minute song with simple lyrics txt; verify chord names land near correct words in output.
