"""Step 2: polyphonic note detection with basic-pitch.

basic-pitch handles chords/polyphony, unlike a monophonic pitch tracker
(e.g. plain librosa.pyin), which is why it's used here instead.

Known limitation: basic-pitch is trained mostly on clean, well-recorded
instruments/vocals. Heavily distorted or very fast electric guitar passages,
extreme vibrato/bends, or leftover separation artifacts from Demucs can
produce spurious or missing notes. onset/frame thresholds below are tuned
to be moderately permissive; tightening them trades recall for precision.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List

from basic_pitch.inference import predict


@dataclass
class Note:
    start: float   # seconds
    end: float     # seconds
    pitch: int     # MIDI note number
    velocity: float  # 0-1 amplitude estimate


def transcribe(audio_path: Path, onset_threshold: float = 0.6,
                frame_threshold: float = 0.4) -> List[Note]:
    _, midi_data, note_events = predict(
        str(audio_path),
        onset_threshold=onset_threshold,
        frame_threshold=frame_threshold,
        minimum_note_length=60,  # ms; shorter than the basic-pitch default
                                  # to keep fast guitar runs/palm-muted notes
    )

    notes = [
        Note(start=start, end=end, pitch=int(pitch), velocity=float(amplitude))
        for start, end, pitch, amplitude, _pitch_bends in note_events
    ]
    # Drop very low-confidence detections — likely Demucs separation artifacts
    notes = [n for n in notes if n.velocity >= 0.12]
    notes.sort(key=lambda n: n.start)
    return notes
