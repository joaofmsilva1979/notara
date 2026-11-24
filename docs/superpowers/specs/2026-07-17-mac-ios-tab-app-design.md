# Mac/iOS Guitar Tab App — Design Spec

Date: 2026-07-17

## Context

An existing Python pipeline (`guitar_tab_pipeline/`, this repo) already turns a
raw audio file into an approximate guitar tab: Demucs source separation,
basic-pitch polyphonic transcription, key detection (chroma +
Krumhansl-Schmuckler), chord detection (beat-synchronous chroma templates),
fretboard mapping (EADGBE heuristic), ASCII tab export, MIDI export, and a
heuristic treble/bass voice split. It has already been run successfully on
"Can Our Time Be Bent" (village claire) — see the `_tab.txt`, `_stems/`, and
`_tab.mid` files next to this doc's parent project.

The goal is to wrap this existing pipeline in a real Mac app (with an
iOS/iPadOS companion), inspired by but improving on
[Capo](https://www.supermegaultragroovy.com/products/capo/mac/).

## Goal & prioritized differentiators

Differentiators vs. Capo, in priority order (most to least important):

1. **Accordage vérifié** — don't blindly assume a tuning; detect and confirm it.
2. **Export PDF imprimable** — proper print layout, not just an editor view.
3. **Transcription & accords corrigeables** — expose and let the user fix the
   underlying note/chord detection, not just chord labels.
4. **Multi-guitares** — expose the existing voice split as two real,
   independently viewable/exportable tabs.
5. **Amélioration continue des modèles** — keep the ML engine upgradable
   independently of the app.
6. **Traitement par lot** — process a folder of songs unattended.

Items 1-3 are the MVP core. Items 4-6 are reduced-scope or explicitly
deferred (see below).

## Platform & architecture

**Approach A (chosen):** the Mac app owns the UI/UX layer (SwiftUI) —
playback sync, editing, tuning confirmation, PDF export. The existing Python
pipeline is reused as-is, packaged as a standalone binary (or bundled Python
runtime) and invoked as a subprocess from the Mac app; it is **not**
reimplemented in Swift/Core ML for v1. The iOS/iPadOS app is a companion
only: it displays and plays back songs already processed on the Mac,
synced via iCloud. There is no on-device audio processing on iOS in v1.

Rejected alternatives:
- **Full native Core ML port** (Demucs + basic-pitch converted to Core ML,
  analysis reimplemented in Swift) — full offline parity on iPhone, but a
  multi-month effort that serves none of the prioritized differentiators.
- **Local-network remote trigger** (iPhone triggers processing on a Mac on
  the same network) — a nice-to-have, deferred; not needed for MVP since the
  Mac is the only device that processes audio anyway.

Non-goals for v1: YouTube/URL audio import (rejected earlier — violates
YouTube's ToS and risks copyright issues; Capo itself only supports local
files), on-device iOS processing, non-Apple platforms (Android/Windows).

## Feature 1 — Accordage vérifié

1. **Before any processing**, the user picks a tuning preset from a short
   list: Standard EADGBE, Drop D, Eb standard, D standard, Drop C#, Open G,
   Open D, or "Other / manual" (6 editable string fields). Defaults to the
   last tuning used.
2. **During analysis**, once notes are transcribed (basic-pitch) and
   fundamental frequencies extracted, the pipeline compares the detected low
   notes / pedal tones against the fingerprint of the selected tuning.
3. **On mismatch** (e.g. Standard chosen but a recurring low D fundamental
   appears and the low E string is never touched), a non-blocking suggestion
   is shown before fretboard mapping: "This doesn't fully match what's
   heard — suggested: Drop D (confidence 82%)", with actions to accept the
   suggestion, keep the original choice, or edit manually.
4. Fretboard mapping (and therefore the tab) is only generated **after**
   this confirmation step.

Implementation touches `key_detection.py` / `fretboard.py`: add a small
catalog of tuning fingerprints and a comparison routine against observed
fundamentals.

## Feature 2 — Export PDF imprimable

- Portrait orientation, Courier New, font size selectable between 7pt and
  8pt (simple menu, not a free slider).
- Rendered natively via PDFKit/Core Text — not HTML-to-PDF — so the
  monospace column alignment that the ASCII tab depends on never drifts
  across viewers/printers.
- Pagination reuses the existing bar-grouping already produced by
  `tab_render.py`; page breaks only ever fall on bar boundaries.
- Each page header shows: song title, key, tempo, tuning, page number. The
  first page also includes a chord-diagram legend (guitar only for MVP) for
  every unique chord used in the song.
- If the multi-guitar voice split (Feature 4) is active, each voice exports
  as its own PDF with the same layout.

## Feature 3 — Transcription & accords corrigeables

- Each transcribed note keeps basic-pitch's confidence score. Notes below a
  threshold (default 0.5, tunable later) are visually flagged on the tab
  (dashed outline / orange tint) so the user's ear is directed to likely
  errors instead of re-checking every note.
- Clicking a flagged (or any) note lets the user reposition it directly on
  the tab (string/fret).
- `chord_detection.py`'s beat-synchronous chroma template matching already
  produces a ranked list of chord candidates per bar, not just the winning
  one. The UI exposes the next 2-3 candidates for a one-click swap instead
  of free-text chord entry.
- Corrections persist in the project file and are not overwritten by a
  pipeline re-run. Exception: changing the confirmed tuning (Feature 1)
  forces the fretboard mapping to regenerate, which discards manual
  *position* corrections (chord corrections survive, since they don't
  depend on tuning).

## Feature 4 — Multi-guitares (reduced MVP scope)

Reuse `voice_split.py`'s existing treble/bass heuristic as-is; expose both
outputs in the app as two independently viewable and exportable tabs. A
true rhythm/lead-aware separation (rather than a register-based heuristic)
is future work, out of scope for v1.

## Feature 5 — Amélioration continue des modèles

Not a UI feature — an architecture constraint. The Python subprocess and its
model dependencies (Demucs, basic-pitch) are versioned independently of the
Mac app bundle, so the engine can be upgraded without rebuilding or
re-releasing the whole app.

## Feature 6 — Traitement par lot (out of MVP scope)

Noted as a future extension only: process an entire folder of songs
unattended. Not designed further here.

## Error handling

The Python subprocess can fail at any pipeline stage (separation,
transcription, key/chord detection, etc.). The app surfaces which specific
stage failed (not a generic error), allows resuming from that stage instead
of restarting the whole pipeline, and retains intermediate files (stems,
etc.) for diagnosis.

## Testing

The existing Python modules (`transcription.py`, `chord_detection.py`,
`key_detection.py`, `fretboard.py`) keep their existing unit-testability.
New Swift-side components (editing, PDF export, tuning flow) are tested
against fixture tabs already generated by the pipeline (e.g. the files
already present in this project) rather than re-running the full pipeline
in every test.
