# Notara Web Platform — Design Spec

**Date:** 2026-08-02
**Status:** Approved for implementation

---

## Goal

Turn the existing Python CLI pipeline into a web platform: users upload audio (or paste a YouTube URL), choose optional hints, and receive synchronized guitar tab + bass tab with playback, downloadable as PDF / TXT / MIDI. Works on desktop and smartphone.

---

## Architecture

**Two-tier, cleanly separated:**

- **Frontend** — static HTML/CSS/JS, zero framework, hosted on GitHub Pages (`joaofmsilva1979.github.io/notara`). Talks to the backend via a REST/WebSocket API.
- **Backend** — FastAPI (Python) app wrapping the existing `pipeline/` modules. Deployed free-tier on Railway or Render. Handles file upload, YouTube fetch, async job processing, and file serving.

No user accounts. No persistent storage. Files are deleted immediately after the job completes.

```
Browser
  │
  ├── GET  /           → GitHub Pages (static HTML)
  ├── POST /api/jobs   → FastAPI: create job (upload or YouTube URL)
  ├── GET  /api/jobs/{id}/status  → poll progress
  ├── GET  /api/jobs/{id}/results → download tab files
  └── WS   /api/jobs/{id}/stream → (optional) live progress push
```

---

## Visual Design

**Color palette — Warm Ruby:**
- Background: `#F8F4F1` (cream)
- Accent / primary: `#B71C1C` (deep ruby red)
- White panels: `#FFFFFF`
- Tab output background: `#FDFAF8`
- Dark section (about): `#1A0808`
- Border: `#E8E0D8`
- Muted text: `#888`

**Typography:** System sans-serif (`'Helvetica Neue', Helvetica, Arial, sans-serif`) for UI. `'Courier New', Courier, monospace` for tab output.

**Logo:** Red `22×22px` rounded square + `NOTARA` in 800-weight, 3px letter-spacing.

---

## Page Structure

```
┌─────────────────────────────────────┐
│  NAV  (sticky)                      │
├─────────────────────────────────────┤
│  TOOL  (split panel / stacked)      │
│  ├── LEFT: upload + options         │
│  └── RIGHT: playback + tab output  │
├─────────────────────────────────────┤
│  ABOUT  (dark section)              │
└─────────────────────────────────────┘
```

---

## Responsive Breakpoints

| Viewport | Layout |
|---|---|
| `≥ 769px` | Split panel — left 42% / right flex |
| `≤ 768px` | Single column — left stacks above right |

On mobile the "right panel" (results) is hidden until processing completes, then revealed below the options.

---

## Left Panel — Upload & Options

### 1. YouTube URL input
- Text input + **Fetch** button
- On Fetch: backend calls `yt-dlp` to download audio, returns a job ID
- Shows spinner + "Fetching audio…" while downloading

### 2. File drop zone (or divider between)
- Accepts: MP3, WAV, M4A, FLAC, OGG, OPUS — up to 100 MB
- Drag-and-drop + "Browse files" button
- On file select: POST to `/api/jobs` with multipart form

### 3. Options (all optional — auto-detected if skipped)

**Tuning** — `<select>` grouped by category:
- Auto-detect *(default)*
- Standard variants: Standard, Std ½↓ (Eb), Std 1↓ (D), Std 1½↓ (C#), Std 2↓ (C)
- Drop: Drop D, Drop C#, Drop C, Drop B, Drop A
- Open: Open G, Open D, Open E, Open A, Open C, DADGAD
- 7-String: Standard (B E A D G B e), Drop A
- 8-String: Standard (F# B E A D G B e), Drop E
- Baritone: B, A
- Bass: Standard EADG, Drop D, 5-String BEADG

**Key** — `<select>` with auto-detect default, then all 12 major + 12 minor keys grouped.

**Multiple guitars** — Yes / No toggle (default: No). Splits stereo L/R channels of Demucs guitar stem.

**Bass tab** — Yes / No toggle (default: No). Outputs separate 4-string bass tab.

**Vocal melody** — Yes / No toggle (default: No). Transcribes the vocal stem as a single-line melody tab in guitar octave range (one octave below actual pitch if needed to fit fretboard). Useful for singers learning parts or guitarists playing the melody.

**Drum summary** — Yes / No toggle (default: No). Outputs a rhythmic pattern summary and ASCII groove map of the drum stem (kick, snare, hi-hat). Does not produce a traditional tab — produces a readable rhythm chart.

**Keyboard / Keys** — Yes / No toggle (default: No). Transcribes the Demucs piano stem (htdemucs_6s separates a dedicated piano stem). Outputs notes as a MIDI file + a simplified note list (pitch + timing). Useful for identifying synth riffs, piano chords, or any keyboard arrangement in the mix. Shows as "Keys" tab in the results panel.

### 4. TRANSCRIBE button
- Disabled until a file or YouTube URL is provided
- On click: submits job, transitions right panel to progress view

---

## Right Panel — Playback & Results

### Progress view (during processing)
Steps shown as a checklist, ticking off in real time. Steps are dynamic — only shown if the corresponding option is enabled:

1. Separating stems (Demucs)
2. Transcribing Guitar 1
3. Transcribing Guitar 2 *(shown only if multi-guitar)*
4. Transcribing bass *(shown only if bass tab)*
5. Transcribing vocal melody *(shown only if vocal melody)*
6. Analysing drums *(shown only if drum summary)*
7. Detecting key & chords
8. Mapping to fretboard + rendering tab

Each step: grey circle → red filled circle with ✓ when done. Estimated time shown: "~2 min".

### Playback bar (shown after processing)
- Play / Pause button (red circle)
- Scrubber with fill progress
- Elapsed / total time
- **Current chord pill** (red, large) + next chord preview
- The browser plays the *original* uploaded audio (served from backend job temp dir)

### Tab output
- Tab switcher: **Guitar 1** | Guitar 2 *(if multi-guitar)* | Bass *(if bass tab)* | Vocals *(if vocal melody)* | Drums *(if drum summary)*
- Tab content: monospace, horizontal scroll on overflow
- **Synchronized highlight**: current bar highlighted with red left border + light red background; past/future bars dimmed to 40% opacity
- Bar advances on each playback tick (based on tempo BPM from pipeline output)
- Header comment lines show detected key, tempo, tuning in red
- **Vocals tab**: single-string melody tab in guitar octave range. Header notes the octave transposition if applied (`# Transposed: -1 octave to fit guitar range`).
- **Drums tab**: ASCII groove map + text summary. No synchronized highlight (beat grid replaces it). Format:
  ```
  # Tempo: 124 BPM · 4/4 · Kick on 1 & 3 · Snare on 2 & 4 · Hi-hat 8ths
  Beat:  1    +    2    +    3    +    4    +
  K:     ●         ●         ●              ●
  S:          ●              ●
  HH:   ●    ●    ●    ●    ●    ●    ●    ●
  ```

### Downloads (per active tab)
- **↓ PDF** (filled red button)
- **↓ TXT** (outline red button)
- **↓ MIDI** (outline grey button — Guitar 1, Guitar 2, Vocals tabs only; not Bass or Drums)

---

## About Section

Dark background (`#1A0808`), positioned below the tool, reachable by scrolling.

**Structure:**
- Section rule (40px red line) + "WHO'S BEHIND THIS" heading + "The why. The how. The what." subline
- Photo (circular, 160px, ruby border, slight contrast boost) + name + role — left on desktop, centered above text on mobile
- Three paragraphs tagged **— Why / — How / — What** (Simon Sinek order)
- Privacy notice with lock icon: "Nothing is saved. Your audio is processed and immediately discarded. No account, no tracking, no storage."
- **Tip jar** — between the privacy notice and the footer (see below)
- Footer: "NOTARA · 2026 · Made with stubbornness and ♥ · Built with Claude"

### Tip Jar

Pay-what-you-want, zero pressure. Inspired by Radiohead's "In Rainbows" model.

**Platform:** Ko-fi (`ko-fi.com/joaosilva` — owner to confirm exact handle at setup)  
**Fallback:** PayPal.me link in small text below the button

**Copy:**
> *"Notara is free. No catch, no account, no ads. If it saved you an hour of ear training and you feel like it — buy me a coffee. If not, no worries. Go play."*

**Visual:**
- Ko-fi button: warm ruby outline style (`☕ Buy me a coffee`), centered
- Below in small muted text: `or via PayPal · paypal.me/joaosilva`
- Both links open in `target="_blank"`
- Positioned between the privacy notice and the footer rule — part of the dark `#1A0808` section

**Copy (draft — owner to edit freely):**

*Why:* "Sometimes you need to work with your ears. Sometimes you need a little help. There's no shame in the second one — every great guitarist learns from transcribing, and transcribing takes time that not everyone has. I made Notara because I wanted that help to exist, and to be honest about what it is: a starting point, not a finished score."

*How:* "Notara runs Demucs to separate the guitar and bass stems from your audio, then uses basic-pitch to transcribe notes, detects the key and chords, and maps everything to a real fretboard — accounting for tuning, position, and whether there's one guitar or two. The output is an actual tab you can play from. Built in Python. Shaped with Claude."

*What:* "Guitar tab. Bass tab. PDF. MIDI. For any tuning — standard, drop, open, 7-string, 8-string. Auto-detected or manually set. Free. Open source."

---

## Backend API

### `POST /api/jobs`
- Body: `multipart/form-data` with `file` OR `youtube_url` (string), plus optional `tuning`, `key`, `multi_guitar` (bool), `bass_tab` (bool), `vocal_tab` (bool), `drum_summary` (bool)
- Response: `{ "job_id": "abc123", "status": "queued" }`
- Server runs job async in a background thread/process

### `GET /api/jobs/{id}/status`
- Response: `{ "status": "queued|running|done|error", "step": 3, "step_label": "Transcribing Guitar 1", "total_steps": 6 }`
- `total_steps` is dynamic — computed from which options were requested
- Frontend polls every 3 seconds

### `GET /api/jobs/{id}/results`
- Response:
  ```json
  {
    "tabs": {
      "guitar1": "...",
      "guitar2": "...",
      "bass": "...",
      "vocals": "...",
      "drums": "..."
    },
    "key": "A minor",
    "tempo": 124.0,
    "tuning": "Standard",
    "bars": [{ "label": "Am", "start_sec": 0.0, "end_sec": 1.93 }]
  }
  ```
- Keys present in `tabs` only if the corresponding option was enabled
- `bars` is used for playback sync; Drums tab uses the same bar array but highlights by beat instead of bar

### `GET /api/jobs/{id}/audio`
- Serves the original uploaded audio file for in-browser playback (temp file, deleted after job TTL)

### `GET /api/jobs/{id}/download/{track}/{format}`
- `track`: `guitar1`, `guitar2`, `bass`
- `format`: `pdf`, `txt`, `midi`
- Serves the generated file as a download

### Job TTL
- All job files (audio, stems, output) deleted 1 hour after job completion
- No database — job state held in memory (dict) — server restarts clear all jobs

---

## SEO & Discoverability

### Domain
Recommended: `notara.io` — short, memorable, `.io` signals a tool. Point DNS to GitHub Pages (`joaofmsilva1979.github.io/notara`) via CNAME record.

### Meta Tags (in `index.html` `<head>`)
```html
<title>Notara — Audio to Guitar Tab</title>
<meta name="description" content="Upload audio or paste a YouTube URL. Notara transcribes guitar tab, bass tab, and vocal melody automatically. Free. No account. Any tuning.">
<meta name="keywords" content="guitar tab, guitartab, guitar tab generator, audio to guitar tab, ultimate guitar alternative, automatic guitar transcription, bass tab from audio, vocal melody tab, multi-guitar transcription, free tab maker">
<link rel="canonical" href="https://notara.io">

<!-- Open Graph -->
<meta property="og:title" content="Notara — Audio to Guitar Tab">
<meta property="og:description" content="Turn any audio into guitar tab. Upload a file or paste a YouTube URL. Free, open source, no account needed.">
<meta property="og:image" content="https://notara.io/og-image.png">
<meta property="og:url" content="https://notara.io">
<meta property="og:type" content="website">

<!-- Twitter Card -->
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="Notara — Audio to Guitar Tab">
<meta name="twitter:description" content="Turn any audio into guitar tab. Free, open source.">
<meta name="twitter:image" content="https://notara.io/og-image.png">

<!-- Schema.org structured data -->
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  "name": "Notara",
  "applicationCategory": "MusicApplication",
  "operatingSystem": "Web",
  "url": "https://notara.io",
  "description": "Automatic guitar tab and bass tab transcription from audio. Free and open source.",
  "offers": { "@type": "Offer", "price": "0" }
}
</script>
```

### Additional SEO files
- `sitemap.xml` at root — single URL (`https://notara.io`) with `lastmod` and `changefreq: monthly`
- `robots.txt` — `Allow: /`, `Sitemap: https://notara.io/sitemap.xml`
- `og-image.png` — 1200×630px social preview card (Warm Ruby, NOTARA wordmark, tagline "Audio → Guitar Tab")

---

## New Pipeline Features Required

The following must be added to the Python pipeline to support the full tuning list:

| Tuning | MIDI values |
|---|---|
| Std 1½ down C# | [37, 42, 47, 52, 56, 61] |
| Std 2 down C | [36, 41, 46, 51, 55, 60] |
| Drop C | [36, 43, 48, 53, 57, 62] |
| Drop B | [35, 42, 47, 52, 56, 61] |
| Drop A | [33, 40, 45, 50, 54, 59] |
| Open E | [40, 47, 52, 56, 59, 64] |
| Open A | [40, 45, 52, 57, 61, 64] |
| Open C | [36, 43, 48, 55, 60, 64] |
| DADGAD | [38, 45, 50, 55, 57, 62] |
| 7-String Standard | [35, 40, 45, 50, 55, 59, 64] |
| 7-String Drop A | [33, 40, 45, 50, 55, 59, 64] |
| 8-String Standard | [30, 35, 40, 45, 50, 55, 59, 64] |
| 8-String Drop E | [28, 35, 40, 45, 50, 55, 59, 64] |
| Baritone B | [35, 40, 45, 50, 54, 59] |
| Baritone A | [33, 38, 43, 48, 52, 57] |

`tab_render.py` and `fretboard.py` already support arbitrary string counts — no changes needed there.

`suggest_alternate_tuning` must not suggest 7/8-string tunings for standard 6-string input.

`yt-dlp` added as a new Python dependency for YouTube download.

### Vocal Melody Transcription

New module: `pipeline/vocal_tab.py`

1. Input: Demucs `vocals` stem path (already produced by `htdemucs_6s`)
2. Run `basic-pitch` on the vocal stem (monophonic or near-monophonic — pitch quality is good)
3. Filter to one note per onset (take highest-confidence pitch per frame window to get a clean melody line)
4. Check pitch range: if median MIDI pitch > 60 (middle C), transpose all notes down one octave (subtract 12) to fit comfortably on standard guitar fretboard (MIDI 40–84)
5. Map to fretboard via existing `fretboard.map_notes_to_fretboard()` using Standard tuning (always — vocals tab is always in standard guitar octave)
6. Render with `tab_render.render_tab()`, inserting a comment header line: `# Vocal melody · Transposed: -1 oct` if octave shift was applied
7. Output: plain-text guitar tab string (same format as guitar1/guitar2)

New CLI flag: `--vocal-tab` (bool, default False)

### Drum Summary

New module: `pipeline/drum_summary.py`

1. Input: Demucs `drums` stem path (already produced by `htdemucs_6s`)
2. Load with `librosa`. Run `librosa.onset.onset_detect()` to get onset frames
3. For each onset, extract a short window (~50ms) and compute mean energy in three frequency bands:
   - Kick: 50–200 Hz (low)
   - Snare: 200–800 Hz (mid, transient character)
   - Hi-hat: 8000+ Hz (sharp, high)
4. Classify each onset as kick / snare / hi-hat / other by dominant band energy
5. Quantize onsets to a beat grid (use detected tempo from `pipeline/key_detection.py` — already computes BPM)
6. Build ASCII pattern string (4/4 grid, 8th-note resolution):
   ```
   Beat:  1    +    2    +    3    +    4    +
   K:     ●              ●
   S:          ●              ●
   HH:   ●    ●    ●    ●    ●    ●    ●    ●
   ```
7. Append a one-line text summary: `"4/4 · kick on 1&3 · snare on 2&4 · hi-hat 8ths"` derived from the dominant pattern
8. Output: string (displayed in Drums tab, not rendered as tab ASCII)

New CLI flag: `--drum-summary` (bool, default False)

New Python dependencies: `librosa` (already used by key_detection for BPM — verify it's in requirements.txt)

---

## Deployment

| Component | Platform | URL |
|---|---|---|
| Frontend | GitHub Pages | `joaofmsilva1979.github.io/notara` |
| Backend | Railway (free tier) or Render | `api.notara.app` or Railway-assigned subdomain |

Frontend `config.js` exports `API_BASE_URL` — set to production backend URL for GitHub Pages build, `http://localhost:8000` for local dev.

---

## Out of Scope (this version)

- User accounts / saved history
- Real-time collaborative editing of tabs
- Mobile app (native iOS/Android)
- Chord diagram visualization (Swaram-style fret diagrams)
- Beginner mode / chord simplification
- BPM / time signature editing
