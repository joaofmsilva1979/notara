"""Vocal melody transcription and tab rendering.

Transcribes a Demucs vocal stem using basic-pitch, optionally transposes
down one octave if the median pitch is above MIDI 60 (middle C), then
renders as a guitar-octave melody tab using the existing pipeline infrastructure.

Known limitations:
- basic-pitch accuracy on vocals depends heavily on stem separation quality.
  Demucs artifacts (leakage from other instruments) can produce spurious notes.
- The octave-down heuristic (median > MIDI 60) is a single global decision;
  it does not handle songs where the vocal alternates between low verses and
  high choruses. The whole stem is shifted or not.
- Very high or very low vocal passages may still fall outside standard guitar
  range after transposition and will be silently dropped by map_notes_to_fretboard.
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Tuple

import numpy as np

from .chord_detection import ChordSegment
from .fretboard import map_notes_to_fretboard
from .key_detection import KeyEstimate
from .tab_render import render_tab
from .transcription import Note, transcribe
from .tuning import STANDARD_E_A_D_G_B_E, find_tuning

GUITAR_RANGE_MIDPOINT = 60  # MIDI middle C; median above this triggers octave shift
OCTAVE_SEMITONES = 12


def _should_transpose(notes: List[Note]) -> bool:
    """Return True if the median pitch of `notes` exceeds GUITAR_RANGE_MIDPOINT."""
    if not notes:
        return False
    return float(np.median([n.pitch for n in notes])) > GUITAR_RANGE_MIDPOINT


def transcribe_vocal_melody(vocal_stem_path: Path) -> Tuple[List[Note], bool]:
    """Transcribe the vocal stem and optionally shift pitches down one octave.

    Returns
    -------
    notes : List[Note]
        Transcribed (and possibly transposed) notes.
    transposed : bool
        True if pitches were shifted down by one octave (12 semitones).
    """
    notes = transcribe(vocal_stem_path)
    transposed = _should_transpose(notes)
    if transposed:
        notes = [
            Note(pitch=n.pitch - OCTAVE_SEMITONES, start=n.start,
                 end=n.end, velocity=n.velocity)
            for n in notes
        ]
    return notes, transposed


def render_vocal_tab(
    vocal_stem_path: Path,
    bars: List[ChordSegment],
    key_estimate: KeyEstimate,
    tempo: float,
    source_name: str,
) -> str:
    """Transcribe the vocal stem and render it as ASCII guitar tab.

    If the median pitch is above MIDI 60, notes are shifted down one octave
    to fit standard guitar range, and a ``# Transposed: -1 octave`` comment
    is injected into the tab header immediately after the tuning line.
    """
    tuning = find_tuning(STANDARD_E_A_D_G_B_E)
    notes, transposed = transcribe_vocal_melody(vocal_stem_path)
    fretted = map_notes_to_fretboard(notes, tuning)
    tab = render_tab(bars, fretted, key_estimate, tempo, source_name, tuning)
    if transposed:
        tab = tab.replace(
            f"# Tuning: {tuning.name}",
            f"# Tuning: {tuning.name}\n# Transposed: -1 octave to fit guitar range",
        )
    return tab
