# Notara — Technical Documentation

## 1. Overview

**Notara** is a free, open-source web platform that converts audio recordings into playable guitar, bass, vocal, and keyboard tabs. Users upload an audio file (MP3, WAV, M4A, FLAC, OGG, OPUS) or paste a YouTube URL; Notara separates the recording into stems with Demucs, transcribes notes with basic-pitch, detects key, tempo, and chord progressions with librosa, and renders the result as classic ASCII tab plus downloadable PDF and MIDI files.

The end-to-end flow: the static frontend collects the audio (or YouTube URL) and processing options, submits a job to the FastAPI backend, polls the job status, and once the pipeline is done, fetches the result JSON and streams the original audio for synchronized in-browser playback. There is no account system, no persistence beyond a one-hour in-memory TTL, and no database.

## 2. Architecture

```
┌───────────────────────────────────────────────────────────────────────────┐
│                          Static Frontend (GitHub Pages)                    │
│                                                                            │
│   index.html · css/main.css · js/config.js · js/app.js · js/playback.js   │
│                                                                            │
│   • Drag/drop audio OR paste YouTube URL                                  │
│   • Options: tuning, key, multi-guitar, bass, vocal, drums, keys          │
│   • Polls /api/jobs/{id}/status every 3 s                                 │
│   • Renders ASCII tab, synchronised playback bar, chord display           │
└───────────────────────────────┬───────────────────────────────────────────┘
                                │  HTTPS · multipart POST · JSON polling
                                ▼
┌───────────────────────────────────────────────────────────────────────────┐
│                    FastAPI Backend (Railway / Render)                      │
│                                                                            │
│   api/main.py    · FastAPI app, CORS, lifespan cleanup                    │
│   api/routes.py  · /api/jobs, /status, /results, /audio, /download        │
│   api/jobs.py    · In-memory Job store (thread-locked, 1 h TTL)           │
│   api/worker.py  · Background pipeline runner                             │
└───────────────────────────────┬───────────────────────────────────────────┘
                                │  BackgroundTasks (in-process)
                                ▼
┌───────────────────────────────────────────────────────────────────────────┐
│                        Pipeline (pipeline/*.py)                            │
│                                                                            │
│   1. separation.py       — Demucs (htdemucs_6s) 6-stem separation         │
│   2. transcription.py    — basic-pitch polyphonic note detection          │
│   3. key_detection.py    — chromagram + Krumhansl-Kessler                 │
│   4. chord_detection.py  — beat-sync chroma + templates + bass root       │
│   5. fretboard.py        — map notes to (string, fret)                    │
│   6. tab_render.py       — ASCII tab rendering (16-slot / bar)            │
│   7. vocal_tab.py · drum_summary.py · piano_tab.py — optional stems       │
└───────────────────────────────────────────────────────────────────────────┘
```

**Data flow:**

1. User selects audio (or pastes YouTube URL), toggles options, clicks *Transcribe*.
2. Frontend `POST`s `multipart/form-data` to `/api/jobs`.
3. Backend creates a `Job` (UUID prefix), copies the upload to a temp work directory, and schedules `worker.run_job` via FastAPI's `BackgroundTasks`.
4. Frontend polls `/api/jobs/{id}/status` every 3 s and renders a stepped progress list.
5. On `status == "done"`, the frontend fetches `/api/jobs/{id}/results` (JSON) and points the `<audio>` element at `/api/jobs/{id}/audio`.
6. `playback.js` runs a `requestAnimationFrame` loop, syncing the current bar highlight and chord display to `audio.currentTime`.
7. Download buttons hit `/api/jobs/{id}/download/{track}/{fmt}`.

## 3. Pipeline Modules

### 3.1 Transcription (`pipeline/transcription.py`)

**Purpose.** Convert an audio stem into a list of pitched note events using Spotify's basic-pitch model, which handles chords and polyphony (unlike a monophonic tracker such as plain `librosa.pyin`).

**Key function.**

```python
def transcribe(
    audio_path: Path,
    onset_threshold: float = 0.5,
    frame_threshold: float = 0.3,
) -> List[Note]
```

| Parameter         | Type    | Description                                                                        |
| ----------------- | ------- | ---------------------------------------------------------------------------------- |
| `audio_path`      | `Path`  | Audio file to transcribe (typically a separated stem).                             |
| `onset_threshold` | `float` | basic-pitch onset threshold. Higher = fewer false onsets, more missed notes.       |
| `frame_threshold` | `float` | basic-pitch frame threshold. Higher = shorter/quieter notes are dropped.           |

**Returns.** `List[Note]` sorted by start time. `Note` is a dataclass with `start` and `end` (seconds), `pitch` (MIDI note number), and `velocity` (0–1 amplitude estimate). `minimum_note_length` is set to 60 ms — shorter than basic-pitch's default — to keep fast runs and palm-muted notes.

**Known limitations.**
- basic-pitch is trained mostly on clean, well-recorded material. Heavily distorted or very fast electric guitar, extreme vibrato/bends, or Demucs leakage artifacts produce spurious or missing notes.
- The onset/frame thresholds above are moderately permissive; tightening them trades recall for precision.

### 3.2 Tuning (`pipeline/tuning.py`)

**Purpose.** Catalogue of guitar and bass tunings (represented as lists of open-string MIDI pitches, lowest string first) plus utilities for fit-scoring and auto-detecting a better tuning.

**Constants.** `MAX_FRET = 15` — the highest fret the pipeline will consider when fretting a note.

**Available tunings.**

| Category    | Name                        | Open strings (low → high)         |
| ----------- | --------------------------- | --------------------------------- |
| Standard    | `Standard EADGBE`           | E A D G B e                       |
| Standard    | `Eb Standard`               | Eb Ab Db Gb Bb eb                 |
| Standard    | `D Standard`                | D G C F A d                       |
| Standard    | `C# Standard`               | C# F# B E G# c#                   |
| Standard    | `C Standard`                | C F Bb Eb G c                     |
| Drop        | `Drop D`                    | D A D G B e                       |
| Drop        | `Drop C#`                   | C# Ab Db Gb Bb eb                 |
| Drop        | `Drop C`                    | C G C F A d                       |
| Drop        | `Drop B`                    | B F# B E G# c#                    |
| Drop        | `Drop A`                    | A E A D F# b                      |
| Open        | `Open G`                    | D G D G B d                       |
| Open        | `Open D`                    | D A D F# A d                      |
| Open        | `Open E`                    | E B E G# B e                      |
| Open        | `Open A`                    | E A E A C# e                      |
| Open        | `Open C`                    | C G C G C e                       |
| Open        | `DADGAD`                    | D A D G A d                       |
| Baritone    | `Baritone B`                | B E A D F# b                      |
| Baritone    | `Baritone A`                | A D G C E a                       |
| Bass        | `Bass Standard EADG`        | E A D G                           |
| Bass        | `Bass Drop D`               | D A D G                           |
| Bass        | `Bass 5-String BEADG`       | B E A D G                         |
| Extended    | `7-String Standard`         | B E A D G B e                     |
| Extended    | `7-String Drop A`           | A E A D G B e                     |
| Extended    | `8-String Standard`         | F# B E A D G B e                  |
| Extended    | `8-String Drop E`           | E B E A D G B e                   |

**Key functions.**

```python
def find_tuning(name: str) -> Tuning
```
Lookup by exact tuning name; raises `ValueError` for unknown names. Searches `TUNINGS + BASS_TUNINGS + EXTENDED_TUNINGS`.

```python
def fit_score(notes: List[Note], tuning: Tuning) -> float
```
Fraction of `notes` whose pitch can be fretted on `tuning` within `[0, MAX_FRET]`. Notes below every string's open pitch (i.e. would require a negative fret) are the strongest signal of a mismatched tuning.

```python
def suggest_alternate_tuning(
    notes: List[Note],
    selected: Tuning,
    min_confidence: float = 0.9,
    min_improvement: float = 0.1,
    min_notes: int = 8,
) -> Optional[TuningSuggestion]
```
Returns a clearly-better-fitting tuning, or `None`. "Clearly better" means the candidate scores at least `min_confidence` **and** beats `selected` by at least `min_improvement`. Bass tunings are kept in a separate list so a bass tuning is never proposed as an alternative for a guitar track.

**Known limitations.**
- Tunings that happen to fit the same notes equally well (e.g. Drop D and D Standard on a song that never touches the lowest string) are indistinguishable.
- Fewer than 8 notes is treated as insufficient signal — a single artifact note could otherwise produce a maximally "confident" suggestion.

### 3.3 Key Detection (`pipeline/key_detection.py`)

**Purpose.** Estimate the song's global key (tonic + major/minor) using a chroma profile correlated against the empirically-derived Krumhansl-Kessler key templates.

**Key function.**

```python
def detect_key(y: np.ndarray, sr: int) -> KeyEstimate
```

| Parameter | Type         | Description                                       |
| --------- | ------------ | ------------------------------------------------- |
| `y`       | `np.ndarray` | Mono audio samples (typically the harmonic mix).  |
| `sr`      | `int`        | Sample rate (Hz).                                 |

**Returns.** `KeyEstimate(tonic: str, mode: str, correlation: float)`. `tonic` is one of `C, C#, D, ..., B`; `mode` is `"major"` or `"minor"`; `correlation` is the Pearson correlation of the best-fitting rotated template against the average chroma profile.

**Algorithm.** Compute a CQT chromagram, average to a 12-bin pitch-class profile, correlate against all 12 rotations of both the major and minor Krumhansl-Kessler profiles, and pick the highest-scoring rotation/mode.

**Known limitations.**
- Global, whole-track estimate — songs that modulate are collapsed to a single key.
- Modal or harmonically ambiguous material (parallel major/minor colour, no clear tonic) can return a "best fit" that disagrees with a human's judgement.

### 3.4 Chord Detection (`pipeline/chord_detection.py`)

**Purpose.** Detect one chord per bar via beat-synchronous chroma template matching, constrained by the separated bass stem's root and by the detected song key, then smoothed with bar-to-bar hysteresis.

**Key function.**

```python
def detect_chords(
    y: np.ndarray,
    sr: int,
    bass_y: Optional[np.ndarray] = None,
    bass_sr: Optional[int] = None,
    key_estimate: Optional[KeyEstimate] = None,
) -> tuple[List[ChordSegment], float]
```

| Parameter      | Type            | Description                                                       |
| -------------- | --------------- | ----------------------------------------------------------------- |
| `y`, `sr`      | `np.ndarray, int` | Mono harmonic mix + sample rate.                                |
| `bass_y`, `bass_sr` | `np.ndarray, int`, optional | Separated bass stem — enables bass-root forcing.  |
| `key_estimate` | `KeyEstimate`, optional | Enables the diatonic-root soft-bonus for ambiguous bars.  |

**Returns.** `(segments, tempo)` — a list of `ChordSegment(bar_index, start, end, label)` and the estimated tempo in BPM. Chord labels come from a bank of 60 templates (12 roots × `""`, `"m"`, `"7"`, `"maj7"`, `"m7"`); silence gets the label `"N.C."`. Root and fifth are weighted 1.0, third/seventh 0.8.

**Bar construction.** `librosa.beat.beat_track` gives beat frames; bars are groups of `BEATS_PER_BAR = 4` beats (i.e. 4/4 assumed). If fewer than 4 beats are detected, a fallback linear grid is generated.

**Refinements.**
- **Bass-root forcing.** For each bar, if a single pitch class holds ≥ `BASS_CLARITY_THRESHOLD = 0.35` of the bass chroma energy, the chord root is forced to that pitch class and only its 5 templates are searched.
- **Diatonic bonus.** If the bass didn't force a root, chord templates whose root is diatonic to `key_estimate` get a small additive score bonus (`DIATONIC_BONUS = 0.03`).
- **Hysteresis smoothing.** A bar whose winning label differs from its predecessor but only narrowly beats the predecessor's label on this bar's own chroma (gap ≤ `HYSTERESIS_MARGIN = 0.05`) is pulled back to the previous label. Bars with a bass-forced root or an `N.C.` label are never altered.

**Known limitations.**
- Only 5 chord qualities × 12 roots (60 templates). sus2/sus4, add9, 6th chords, altered dominants, and inversions are not modelled and are misclassified as the closest template.
- Meter is assumed constant 4/4. Tempo/meter changes, pickup bars, or inaccurate beat tracking will shift bar boundaries.
- One chord label per bar — genuine intra-bar changes collapse into a single "best fit".
- Bass-root forcing assumes the bass plays the chord root; pedal tones or non-root doubling can force an incorrect root.
- Diatonic bonus inherits any error from `key_detection`.
- Hysteresis can drift a long run of ambiguous bars toward an early bar's read.

### 3.5 Fretboard Mapping (`pipeline/fretboard.py`)

**Purpose.** Assign each detected note (or near-simultaneous group of notes) to a `(string, fret)` position for a given tuning, preferring low frets and grouping notes that fall within a 4-fret position window.

**Key function.**

```python
def map_notes_to_fretboard(
    notes: List[Note],
    tuning: Optional[Tuning] = None,
) -> List[FrettedNote]
```

| Parameter | Type      | Description                                                       |
| --------- | --------- | ----------------------------------------------------------------- |
| `notes`   | `List[Note]` | Notes from `transcription.transcribe`.                          |
| `tuning`  | `Tuning`, optional | Defaults to `Standard EADGBE`.                          |

**Returns.** `List[FrettedNote]` sorted by start time. `FrettedNote(string, fret, start, end, pitch)` — `string=0` is the lowest-pitched string.

**Algorithm.**
- Group notes whose onsets fall within `CHORD_TOLERANCE = 0.05` s into "chord grasps".
- Within a grasp, assign highest pitches first (fewer valid options → fewer collisions).
- First pass: prefer open strings or frets inside the current `POSITION_SPAN = 4`-fret window.
- Second pass: fall back to the lowest available fret on any free string.
- Shift the window if the chosen fret lies outside it.

**Known limitations.**
- No physical playability model — hand span, barre shapes, open-string ringing, idiomatic fingerings are ignored.
- Out-of-range notes and excess notes in an over-full chord are silently dropped.
- The fixed 0.05 s grouping tolerance can split arpeggios or merge quick separate notes into a single "chord".

### 3.6 Tab Rendering (`pipeline/tab_render.py`)

**Purpose.** Render fretted notes + chord labels + key/tempo header into a classic multi-line ASCII tab, one bar per 16-slot grid.

**Key functions.**

```python
def render_tab(
    bars: List[ChordSegment],
    notes: List[FrettedNote],
    key_estimate: KeyEstimate,
    tempo: float,
    source_name: str,
    tuning: Tuning = None,
    bars_per_line: int = 4,
) -> str
```

| Parameter        | Type    | Description                                                           |
| ---------------- | ------- | --------------------------------------------------------------------- |
| `bars`           | `List[ChordSegment]` | Output of `chord_detection.detect_chords`.                |
| `notes`          | `List[FrettedNote]` | Output of `fretboard.map_notes_to_fretboard`.              |
| `key_estimate`   | `KeyEstimate` | For the header line.                                              |
| `tempo`          | `float` | BPM, for the header line.                                             |
| `source_name`    | `str`   | Human-readable filename shown in the header.                          |
| `tuning`         | `Tuning` | Defaults to `Standard EADGBE`.                                       |
| `bars_per_line`  | `int`   | Number of bars per rendered line. The web UI uses `1` so that the playback highlight can target a single `<span class="tab-bar">` per bar. |

**Returns.** The full tab as a single string.

```python
def write_tab(path: Path, bars, notes, key_estimate, tempo, source_name, tuning=None) -> None
```
Convenience wrapper that renders and writes to `path` as UTF-8.

**Grid.** `COLUMNS_PER_BAR = 16` (16th-note grid, 4/4 assumed), `CELL_WIDTH = 3` characters per cell.

**Known limitations.**
- Rhythm is only approximate — ASCII tab shows fret position, not duration. Anything not roughly 16th-note-aligned in 4/4 (swing, triplets, odd meters, tempo changes) will be misrepresented.
- Two notes snapped to the same slot on the same string collide silently — the later one overwrites the earlier one.

### 3.7 Vocal Melody (`pipeline/vocal_tab.py`)

**Purpose.** Transcribe the Demucs vocal stem with basic-pitch, transpose down one octave if the melody is above guitar range, then render as a single-line melody tab using `tab_render`.

**Key functions.**

```python
def transcribe_vocal_melody(vocal_stem_path: Path) -> Tuple[List[Note], bool]
```
Returns `(notes, transposed)` where `transposed=True` if the median pitch exceeded `GUITAR_RANGE_MIDPOINT = 60` (MIDI middle C) and pitches were shifted down `OCTAVE_SEMITONES = 12`.

```python
def render_vocal_tab(
    vocal_stem_path: Path,
    bars: List[ChordSegment],
    key_estimate: KeyEstimate,
    tempo: float,
    source_name: str,
    tuning: Optional[Tuning] = None,
    bars_per_line: int = 4,
) -> str
```
Transcribes, transposes if appropriate, maps to fretboard, and renders. If transposed, injects `# Transposed: -1 octave to fit guitar range` after the tuning header line.

**Known limitations.**
- Vocal transcription quality is bounded by Demucs isolation quality — bleed from other instruments produces spurious notes.
- The octave-down decision is a single global decision — songs that alternate between low verses and high choruses are shifted (or not) uniformly.
- Vocal passages that remain outside guitar range after transposition are silently dropped by `map_notes_to_fretboard`.

### 3.8 Drum Summary (`pipeline/drum_summary.py`)

**Purpose.** Detect drum onsets in a Demucs drums stem, classify each as kick / snare / hi-hat by frequency-band energy, and render an 8-slots-per-bar ASCII groove map plus a one-line pattern description.

**Key function.**

```python
def summarize_drums(drum_stem_path: Path, tempo: float) -> str
```
Runs onset detection with `librosa.onset.onset_detect`, classifies each onset by comparing mean FFT energy in the kick (50–200 Hz), snare (200–800 Hz), and hi-hat (8000 Hz → Nyquist) bands over a 50 ms window. Onsets are quantised to an 8-slot-per-bar grid. If no onsets are detected, returns `"(No drum onsets detected)"`.

**Returns.** Multi-line string with a `# Tempo: N BPM · <description>` header followed by the ASCII pattern. `n_bars` in the grid is `max(4, min(8, int(last_onset / bar_sec) + 1))`.

**Known limitations.**
- Classification is a frequency-band heuristic, not a trained classifier. Toms, cymbals, and percussion outside the three bands are forced into K/S/H.
- Hi-hat band is unreachable at sample rates below 16 kHz — hi-hat energy is treated as zero in that case.
- Assumes 4/4; the grid uses 60 s / (tempo × 4) as bar length.

### 3.9 Keyboard/Piano MIDI (`pipeline/piano_tab.py`)

**Purpose.** Transcribe the Demucs piano stem into a per-note listing (bar/beat/pitch/duration) and, if `mido` is installed, into a downloadable Standard MIDI File.

**Key function.**

```python
def render_piano_tab(
    piano_path: Path,
    bars: int,
    key_est: str,
    tempo: float,
    source_name: str,
) -> Optional[Dict[str, Any]]
```

Returns `{"text": str, "midi_bytes": bytes}`, or `None` if the piano stem file is missing or transcription returned zero notes. `midi_bytes` is `b""` when `mido` is unavailable.

**Text format.** Header (`Keys — N notes detected — tempo: BPM`), then one line per note:
```
  Bar   1  Beat 1.0  C4    (0.42s)
```
Tempo ≤ 0 is defensively coerced to 120 BPM. Bar/beat are computed assuming 4/4.

**Known limitations.**
- Quality depends heavily on Demucs's `piano` stem isolation. Non-piano keyboards (organ, synth) may separate poorly.
- Silent stems return `None`; the caller (`worker.py`) treats that as "keys not available".
- Output is a note listing, not a rendered piano tab — MIDI is the intended downstream artefact.

## 4. API Reference

### 4.1 Base URL

| Environment  | URL                                                                       |
| ------------ | ------------------------------------------------------------------------- |
| Local        | `http://localhost:8000`                                                   |
| Production   | `https://api.notara.app` (configurable — see `js/config.js`)              |

All endpoints are mounted under the `/api` prefix.

### 4.2 Endpoints

#### 4.2.1 `POST /api/jobs` — create a new transcription job

Creates a job, stores the uploaded audio (or the YouTube URL) in a per-job temp directory, and schedules the pipeline in the background.

**Request** — `multipart/form-data`:

| Field           | Type    | Required        | Default            | Description                                                        |
| --------------- | ------- | --------------- | ------------------ | ------------------------------------------------------------------ |
| `file`          | file    | one of file / URL | —                | Audio upload. Allowed extensions: `.mp3 .wav .m4a .flac .ogg .opus` |
| `youtube_url`   | string  | one of file / URL | —                | YouTube URL to be downloaded server-side with `yt-dlp`.            |
| `tuning`        | string  | no              | `"Standard EADGBE"` | Any name from `pipeline.tuning`, or `"auto"` to auto-detect.       |
| `key`           | string  | no              | `"auto"`           | `"auto"` or `"<Tonic> <mode>"`, e.g. `"E minor"`.                  |
| `multi_guitar`  | bool    | no              | `false`            | Split stereo guitar stem into two mono tabs.                       |
| `bass_tab`      | bool    | no              | `false`            | Additionally render a bass tab (Bass Standard EADG).               |
| `vocal_tab`     | bool    | no              | `false`            | Additionally render a vocal-melody tab.                            |
| `drum_summary`  | bool    | no              | `false`            | Additionally render an ASCII drum-groove summary.                  |
| `keys_tab`      | bool    | no              | `false`            | Additionally render a piano note listing (+ MIDI).                 |

**Response** — `200 OK`:

```json
{ "job_id": "a1b2c3d4", "status": "queued" }
```

**Errors.**

| Status | Cause                                                              |
| ------ | ------------------------------------------------------------------ |
| `400`  | Neither `file` nor `youtube_url` provided.                         |
| `400`  | Uploaded `file` has an unsupported extension.                      |

#### 4.2.2 `GET /api/jobs/{job_id}/status` — poll job progress

**Response** — `200 OK`:

```json
{
  "status":     "running",
  "step":        3,
  "step_label": "Detecting key & chords",
  "total_steps": 6,
  "error":       ""
}
```

| Field         | Type    | Description                                                             |
| ------------- | ------- | ----------------------------------------------------------------------- |
| `status`      | string  | `"queued" | "running" | "done" | "error"`                               |
| `step`        | int     | Current step index (1-based).                                           |
| `step_label`  | string  | Human-readable label of the current step (e.g. `"Separating stems (Demucs)"`). |
| `total_steps` | int     | Total step count for this job (depends on which options were enabled).  |
| `error`       | string  | Populated when `status == "error"` — string form of the exception.      |

**Errors.** `404` if `job_id` unknown or already cleaned up (jobs expire 1 h after creation).

#### 4.2.3 `GET /api/jobs/{job_id}/results` — get completed results

**Response** — `200 OK`. See [4.4 Results Schema](#44-results-schema).

**Errors.**

| Status | Cause                                                            |
| ------ | ---------------------------------------------------------------- |
| `404`  | Job not found or expired.                                        |
| `409`  | Job is still `queued`, `running`, or in `error` state.           |

#### 4.2.4 `GET /api/jobs/{job_id}/audio` — stream the original audio

Returns a `FileResponse` for the uploaded (or YouTube-downloaded) source audio. Used by the frontend `<audio>` element for synchronised playback.

**Errors.**

| Status | Cause                                                            |
| ------ | ---------------------------------------------------------------- |
| `404`  | Job not found, or no `audio.*` file present in the work dir.     |
| `409`  | Job is not `done` yet.                                           |

#### 4.2.5 `GET /api/jobs/{job_id}/download/{track}/{fmt}` — download a rendered file

**Path parameters.**

| Parameter | Type   | Description                                                                   |
| --------- | ------ | ----------------------------------------------------------------------------- |
| `job_id`  | string | Job ID.                                                                       |
| `track`   | string | One of: `guitar1 · guitar2 · bass · vocals · keys · drums`.                   |
| `fmt`     | string | One of: `pdf · txt · midi`.                                                  |

**Response.** `FileResponse` for `{track}.{fmt}` from the job's work directory, with `Content-Disposition: attachment; filename="{track}.{fmt}"`.

**Errors.**

| Status | Cause                                                                   |
| ------ | ----------------------------------------------------------------------- |
| `400`  | `track` not in the allowed set, or `fmt` not in the allowed set.        |
| `400`  | `track == "drums"` with `fmt != "txt"` (drums only support `txt`).      |
| `404`  | Job not found or the requested file does not exist for this track.      |
| `409`  | Job is not `done` yet.                                                  |

### 4.3 Job Status Model

`api.jobs.Job` (in-memory, thread-locked dataclass — no database):

| Field         | Type                     | Default                        | Description                                              |
| ------------- | ------------------------ | ------------------------------ | -------------------------------------------------------- |
| `job_id`      | `str`                    | random 8-char UUID prefix      | Public job identifier.                                   |
| `status`      | `str`                    | `"queued"`                     | `queued | running | done | error`.                       |
| `step`        | `int`                    | `0`                            | Current step (1-based).                                  |
| `total_steps` | `int`                    | `6`                            | Recomputed by `worker._count_steps` from the enabled options. |
| `step_label`  | `str`                    | `""`                           | Human-readable label of current step.                    |
| `error`       | `str`                    | `""`                           | Populated when the worker raises.                        |
| `work_dir`    | `Optional[Path]`         | fresh `tempfile.mkdtemp(...)`  | Per-job scratch directory. Deleted on cleanup.           |
| `results`     | `Optional[Dict[str, Any]]` | `None`                       | Populated when `status == "done"` — see [4.4](#44-results-schema). |
| `created_at`  | `float`                  | `time.time()`                  | Epoch seconds. Used to enforce a 1 h TTL.                |

Jobs older than 3600 s are removed on FastAPI startup (`jobs.cleanup_expired`, wired into the app lifespan).

### 4.4 Results Schema

Returned by `GET /api/jobs/{id}/results` and consumed by `js/app.js`:

```jsonc
{
  "tabs": {
    "guitar1": "<ASCII tab string>",
    "guitar2": "<ASCII tab string>",   // present only if multi_guitar was requested
    "bass":    "<ASCII tab string>",   // present only if bass_tab was requested
    "vocals":  "<ASCII tab string>",   // present only if vocal_tab was requested and the vocal stem exists
    "drums":   "<ASCII groove map>",   // present only if drum_summary was requested and the drum stem exists
    "keys":    "<text note listing>"   // present only if keys_tab was requested and the piano stem yielded notes
  },
  "key":   "E minor",
  "tempo": 128.4,
  "tuning": "Drop D",
  "bars": [
    { "label": "Em",  "start_sec": 0.0,   "end_sec": 1.875 },
    { "label": "G",   "start_sec": 1.875, "end_sec": 3.75  }
    // ...
  ]
}
```

| Field       | Type                      | Description                                                                  |
| ----------- | ------------------------- | ---------------------------------------------------------------------------- |
| `tabs`      | `object<string, string>`  | Rendered tabs by track. Only the tracks the user requested (plus always `guitar1`) are populated. Values are `bars_per_line=1` ASCII strings so the frontend can highlight per-bar. |
| `key`       | `string`                  | `"<Tonic> <mode>"`, from `KeyEstimate.__str__`.                              |
| `tempo`     | `float`                   | Estimated BPM, rounded to 1 decimal.                                         |
| `tuning`    | `string`                  | Resolved tuning name (after `"auto"` resolution and `suggest_alternate_tuning`). |
| `bars`      | `array<{label,start_sec,end_sec}>` | Per-bar chord + timing. Consumed by `playback.js` for bar highlighting and chord display. Times are seconds, rounded to 3 decimals. |

## 5. Frontend

### 5.1 File Structure

| File                    | Purpose                                                                          |
| ----------------------- | -------------------------------------------------------------------------------- |
| `index.html`            | Single-page markup: nav, left panel (input + options), right panel (result state machine). Includes SEO metadata, PWA manifest link, and `application/ld+json` `SoftwareApplication` schema. |
| `css/main.css`          | Full Warm Ruby design system. No CSS framework.                                  |
| `js/config.js`          | `API_BASE_URL` auto-detection. Loaded before `app.js`.                           |
| `js/app.js`             | Main application logic — file/URL selection, toggles, submission, polling, results rendering, download buttons, PWA install prompt. |
| `js/playback.js`        | Synchronised playback bar, RAF loop, per-bar tab highlight, chord display.       |
| `manifest.json`         | PWA manifest.                                                                    |
| `icon-192.png` / `icon-512.png` | PWA icons.                                                               |
| `notara-logo.png`       | Nav logo.                                                                        |
| `og-image.svg`          | Open Graph card.                                                                 |
| `robots.txt`, `sitemap.xml` | SEO.                                                                         |

There is **no framework and no build step**. The frontend is plain HTML, CSS, and vanilla ES module–free JavaScript, served as-is by GitHub Pages from the repository root.

### 5.2 Configuration (`js/config.js`)

```js
const API_BASE_URL = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
  ? 'http://localhost:8000'
  : 'https://api.notara.app';
```

- If the page is served from `localhost` or `127.0.0.1`, the backend URL is the local dev server (`http://localhost:8000`).
- Otherwise the frontend hits the production API host baked into this file (`https://api.notara.app` by default).

There is no `.env` — updating the production API URL is a source edit of this file followed by a redeploy of the static site (see [6.6](#66-updating-the-production-api-url)).

### 5.3 Application Flow (`js/app.js`)

1. **Input.** The user either drags a file onto `#drop-zone`, clicks *Browse files*, or types/pastes a YouTube URL into `#yt-input`. Selecting one clears the other. `_setFile(file)` updates `#file-indicator` and enables the *Transcribe* button.
2. **Toggles.** Each yes/no option (multi-guitar, bass, vocal, drums, keys) is a pair of `[data-val]` buttons; `_setupToggle(id, key)` wires up state in the shared `toggleState` object and updates the two buttons' classes.
3. **Submit.** `_submitJob()` builds a `FormData` with the file (or URL) plus every option (`tuning`, `key`, and all five booleans), `POST`s it to `${API_BASE_URL}/api/jobs`, stores the returned `job_id` in `currentJobId`, and calls `_startPolling()`.
4. **Polling.** `_startPolling()` sets a 3-second `setInterval` calling `_poll()`, which `GET`s `/api/jobs/{id}/status` and calls `_updateProgress(data)`. `_updateProgress` renders a `total_steps`-long list of dots (`done`, `active`, or pending) with per-step labels. On `status === "done"` the timer is cleared and `_loadResults()` is invoked; on `"error"` `_showError(...)` is called.
5. **Results rendering.** `_loadResults()` `GET`s `/api/jobs/{id}/results`, stores it in `resultsData`, calls `_renderResults(data)`, and points `#audio-player.src` at `/api/jobs/{id}/audio`. It then calls `window.initPlayback(audio, resultsData.bars)` and switches the UI to the `results` state.
6. **Tabs.** `_renderResults` builds a tab switcher (`Guitar 1 · Guitar 2 · Bass · Vocals · Drums · Keys`) — only the tracks present in `data.tabs` get a button. Clicking a button calls `_switchTab(track, allTracks)`, updates `activeTab`, and re-renders. `_renderTab` splits the ASCII by blank lines: `#`-only segments render as `.tab-comment`; everything else renders as a `.tab-bar` `<span>` (this is the element `playback.js` highlights per-bar).
7. **Downloads.** `tabDownloads` gets buttons based on the active track: PDF and TXT for everything except drums, plus MIDI for guitar1/guitar2/vocals/keys. Drums are TXT-only. Clicking a button opens `/api/jobs/{id}/download/{track}/{fmt}` in a new tab.
8. **PWA install.** `beforeinstallprompt` is captured, `#btn-pwa-install` is revealed, and clicking it fires the browser's install prompt.

### 5.4 Playback (`js/playback.js`)

```js
function initPlayback(audioEl, bars) { ... }
```

- Called by `app.js` once results have loaded. `audioEl` is the `<audio id="audio-player">` element; `bars` is `resultsData.bars` (array of `{label, start_sec, end_sec}`).
- On first call, wires up `play`, `pause`, `ended`, `loadedmetadata` on the audio element, the play button click, and the scrubber click-to-seek handler. Subsequent calls just replace `_audio` and `_bars` and invalidate `_tabBarCache`.

**RAF loop.**

```js
function _tick() {
  _updateTime();
  _syncTab();
  _rafId = requestAnimationFrame(_tick);
}
```

- Started on `play`, cancelled on `pause`/`ended`.
- `_updateTime` refreshes the scrubber fill and the `M:SS / M:SS` time display.
- `_syncTab` finds the active bar (the first `bar` where `bar.start_sec ≤ currentTime < bar.end_sec`, clamped to the last bar past the end), updates `#chord-now` / `#chord-next`, and — unless the active track is `drums` — walks `#tab-content .tab-bar` spans, adding `.active` to the active bar and `.dim` to the rest, then `scrollIntoView({block: 'nearest', behavior: 'smooth'})` on the active bar. The bar span list is cached in `_tabBarCache` and invalidated whenever `initPlayback` is called again.

### 5.5 Design System

**Warm Ruby palette** (`:root` in `css/main.css`):

| Token          | Value                        | Role                              |
| -------------- | ---------------------------- | --------------------------------- |
| `--red`        | `#B71C1C`                    | Primary accent, CTAs, drop border |
| `--red-light`  | `rgba(183,28,28,0.10)`       | Hover / drag-over background      |
| `--cream`      | `#F8F4F1`                    | App background                    |
| `--border`     | `#E8E0D8`                    | Panel and card borders            |
| `--text`       | `#1a1a1a`                    | Primary text                      |
| `--muted`      | `#888`                       | Secondary text                    |
| `--dim`        | `#bbb`                       | Tertiary text                     |
| `--white`      | `#fff`                       | Cards, nav                        |
| `--tab-bg`     | `#FDFAF8`                    | Right panel / tab surface         |
| `--dark-bg`    | `#1A0808`                    | Dark accents                      |

**Typography.** `'Helvetica Neue', Helvetica, Arial, sans-serif`. No web fonts — everything relies on the system stack.

**Breakpoints.**

| Range           | Behaviour                                                                              |
| --------------- | -------------------------------------------------------------------------------------- |
| `> 768 px`      | Two-column layout: `.panel-left` 42% (min 300 px), `.panel-right` fills remaining.     |
| `≤ 768 px`      | Panels stack vertically. Right panel hidden until results arrive (`.panel-right.hidden` removed on `_loadResults`). |
| `≤ 500 px`      | `.nav-sub` is hidden to save nav space.                                                |

## 6. Deployment

### 6.1 Local Development

**Prerequisites.**
- Python 3.10+ (for `basic-pitch`, `demucs`, and `fastapi`).
- `yt-dlp` and `ffmpeg` available on `PATH` (only required for YouTube URL input).
- Any static file server for the frontend (Python's `http.server` is fine).

**Install backend dependencies.**

```bash
pip install -r api/requirements.txt
```

**Start the backend.**

```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

**Serve the frontend.**

```bash
python -m http.server 8080
```

Open `http://localhost:8080`. `js/config.js` auto-detects `localhost` and points the frontend at `http://localhost:8000` for the API.

### 6.2 Frontend — GitHub Pages

The frontend is already configured for GitHub Pages, served from `main` at the repo root.

1. Push to `main` on GitHub.
2. In *Settings → Pages*, set *Source* to `Deploy from a branch`, branch `main`, folder `/ (root)`.
3. GitHub Pages serves `index.html` and all sibling static assets (`css/`, `js/`, `notara-logo.png`, `manifest.json`, `icon-*.png`, `og-image.svg`, `robots.txt`, `sitemap.xml`) as-is. No build step.

URL structure: everything is at the site root — `/index.html`, `/js/app.js`, `/css/main.css`, etc.

### 6.3 Backend — Railway

`api/railway.toml`:

```toml
[build]
builder = "nixpacks"

[deploy]
startCommand = "uvicorn api.main:app --host 0.0.0.0 --port $PORT"
restartPolicyType = "on-failure"
restartPolicyMaxRetries = 3

[build.env]
PYTHONPATH = "."
```

**Steps.**

1. Create a Railway project and link this repository.
2. Point the project's root directory at the repo (Railway will pick up `api/requirements.txt` automatically via nixpacks; ensure the service root or watchpath includes the `api/` folder).
3. Confirm `PYTHONPATH=.` is set (from `[build.env]`) so `api.main:app` and the `pipeline` package resolve.
4. Deploy. Railway will build with nixpacks, install from `api/requirements.txt`, and run the start command.
5. Set a public domain on the Railway service, then update `js/config.js` (see [6.6](#66-updating-the-production-api-url)).

### 6.4 Backend — Render (alternative)

`api/render.yaml`:

```yaml
services:
  - type: web
    name: notara-api
    runtime: python
    buildCommand: pip install -r api/requirements.txt
    startCommand: uvicorn api.main:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: PYTHONPATH
        value: .
    disk:
      name: notara-tmp
      mountPath: /tmp
      sizeGB: 1
```

**Steps.**

1. In the Render dashboard, choose *New → Blueprint* and point it at this repository.
2. Render will detect `api/render.yaml` and provision a Python web service plus a 1 GB disk mounted at `/tmp` (job scratch space).
3. Confirm and deploy.
4. Once assigned a public URL, update `js/config.js` (see [6.6](#66-updating-the-production-api-url)).

An `api/Procfile` (`web: uvicorn api.main:app --host 0.0.0.0 --port $PORT`) is also present for Heroku-style buildpacks.

### 6.5 Environment Variables

| Variable      | Where set                                 | Purpose                                                                   |
| ------------- | ----------------------------------------- | ------------------------------------------------------------------------- |
| `PORT`        | Set by the platform (Railway/Render)      | Interpolated into the `uvicorn ... --port $PORT` start command.           |
| `PYTHONPATH`  | `railway.toml` and `render.yaml`          | Set to `.` so `api.main:app` and the `pipeline` package resolve from the repo root. |

No secrets or API keys are required — Notara has no third-party service dependencies at runtime other than PyPI packages.

### 6.6 Updating the Production API URL

`js/config.js` hard-codes the production API host. To change it:

1. Edit the fallback branch of `API_BASE_URL` in `js/config.js`:
   ```js
   const API_BASE_URL = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
     ? 'http://localhost:8000'
     : 'https://your-new-api-host.example.com';
   ```
2. Commit and push to `main`.
3. GitHub Pages redeploys automatically.

The backend's CORS policy is `allow_origins=["*"]` (see `api/main.py`), so no matching change is required server-side.

## 7. Testing

**Framework.** `pytest` (standard `tests/test_*.py` layout).

**Run all tests.**

```bash
pytest
```

**Run a single module.**

```bash
pytest tests/test_chord_detection.py
```

**Test file map.**

| Test file                       | Coverage                                                                    |
| ------------------------------- | --------------------------------------------------------------------------- |
| `tests/test_api_jobs.py`        | `api/jobs.py` — job creation, retrieval, TTL cleanup, temp dir lifecycle.   |
| `tests/test_api_routes.py`      | `api/routes.py` — endpoint behaviour, error responses, validation.          |
| `tests/test_chord_detection.py` | `pipeline/chord_detection.py` — templates, bass-root forcing, diatonic bonus, hysteresis. |
| `tests/test_drum_summary.py`    | `pipeline/drum_summary.py` — banding classification, grid layout.           |
| `tests/test_fretboard.py`       | `pipeline/fretboard.py` — mapping, position windowing, chord grasps.        |
| `tests/test_main_args.py`       | CLI entry point (`main.py`) argument handling.                              |
| `tests/test_pdf_export.py`      | `pipeline/pdf_export.py` — PDF rendering.                                   |
| `tests/test_piano_tab.py`       | `pipeline/piano_tab.py` — text listing + MIDI bytes (with/without mido).    |
| `tests/test_tab_render.py`      | `pipeline/tab_render.py` — grid layout, chord labels, header lines.         |
| `tests/test_tuning.py`          | `pipeline/tuning.py` — catalog lookups, fit scoring, tuning suggestion.     |
| `tests/test_vocal_tab.py`       | `pipeline/vocal_tab.py` — transpose heuristic, transposition header.        |

## 8. Known Limitations

Compiled from the module docstrings — each downstream stage is bounded by the accuracy of the upstream stages.

- **Rhythm is approximate in ASCII tab.** The tab renderer uses a fixed 16-slot grid per bar, assuming 4/4. Notes are snapped to the nearest slot; duration information is discarded. Swing, triplets, odd meters, and tempo changes are misrepresented.
- **Key detection is global.** A single tonic/mode is estimated for the whole track. Songs that modulate, or that are modal/ambiguous, can get a "best fit" that a human would disagree with.
- **basic-pitch struggles with distorted guitar.** The model is trained mostly on clean material; heavy distortion, fast passages, extreme vibrato/bends, and Demucs artifacts produce spurious or missing notes.
- **Drum classification is a frequency-band heuristic.** Kick (50–200 Hz), snare (200–800 Hz), and hi-hat (8 kHz+) energy is compared per onset. Toms, cymbals, and non-standard percussion are forced into K/S/H. Hi-hat is unreachable below a 16 kHz sample rate.
- **Piano stem quality depends on Demucs separation.** The `htdemucs_6s` piano stem quality varies with source material; non-piano keyboards (organ, synth) may separate poorly, and silent stems return `None` (keys tab is dropped from the results).
- **Chord vocabulary is limited to 60 templates** (12 roots × 5 qualities). sus2/sus4, add9, 6ths, altered dominants, and inversions are misclassified as the nearest template.
- **Meter is assumed constant 4/4.** Everything from bar boundaries to chord windows to the drum grid depends on this.
- **Fretboard mapping ignores physical playability.** Hand span, barre shapes, open-string ringing, and idiomatic fingerings are not modelled.

## 9. License & Credits

**License.** Open source. See `LICENSE` in the repo root (or the GitHub project page).

**Built with Python and Claude.**

**Key dependencies** (see `api/requirements.txt`):

| Package         | Role in Notara                                                          |
| --------------- | ----------------------------------------------------------------------- |
| `demucs`        | 6-stem source separation (`htdemucs_6s`).                               |
| `basic-pitch`   | Polyphonic note transcription for guitar, bass, vocals, and piano.       |
| `librosa`       | Chromagram, key detection, beat tracking, onset detection.               |
| `soundfile`     | Reading and writing WAV stems.                                          |
| `mido`          | Standard MIDI File export for guitar and keys tracks.                    |
| `numpy`, `scipy` | Numerical backbone.                                                    |
| `reportlab`     | PDF export.                                                             |
| `fastapi`       | Web framework.                                                          |
| `uvicorn`       | ASGI server.                                                            |
| `python-multipart` | Multipart form parsing for file uploads.                             |
| `yt-dlp`        | YouTube audio download.                                                 |
