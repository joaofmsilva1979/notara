"""Piano/keyboard note transcription via Basic-Pitch on the Demucs piano stem."""
from __future__ import annotations

import io
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import mido
    _HAS_MIDO = True
except ImportError:
    _HAS_MIDO = False

from pipeline.transcription import transcribe

_MIDI_NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def _pitch_name(midi_note: int) -> str:
    octave = (midi_note // 12) - 1
    name = _MIDI_NOTE_NAMES[midi_note % 12]
    return f"{name}{octave}"


def _notes_to_text(notes: list, bars: int, tempo: float) -> str:
    if tempo <= 0:
        tempo = 120.0
    # Find pitch range
    pitches = sorted({n.pitch for n in notes})
    lo = _pitch_name(pitches[0]) if pitches else "?"
    hi = _pitch_name(pitches[-1]) if pitches else "?"
    return (
        f"Keys / Piano — {len(notes)} notes detected\n"
        f"Range: {lo} – {hi}  ·  Tempo: {tempo:.0f} BPM\n"
        f"\n"
        f"Download the MIDI file to view and edit in your DAW."
    )


def _notes_to_midi(notes: list, tempo: float) -> bytes:
    if not _HAS_MIDO:
        return b""
    if tempo <= 0:
        tempo = 120.0

    mid = mido.MidiFile(type=0)
    track = mido.MidiTrack()
    mid.tracks.append(track)
    track.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(tempo), time=0))

    ticks_per_beat = mid.ticks_per_beat
    seconds_per_tick = 60.0 / (tempo * ticks_per_beat)

    events: List[tuple] = []
    for note in notes:
        events.append((note.start, "note_on", note.pitch))
        events.append((note.end, "note_off", note.pitch))

    events.sort(key=lambda e: e[0])
    last_time = 0.0
    for abs_time, msg_type, pitch in events:
        delta_s = abs_time - last_time
        delta_ticks = int(delta_s / seconds_per_tick)
        track.append(mido.Message(msg_type, note=pitch, velocity=64, time=delta_ticks))
        last_time = abs_time

    buf = io.BytesIO()
    mid.save(file=buf)
    return buf.getvalue()


def render_piano_tab(
    piano_path: Path,
    bars: int,
    key_est: str,
    tempo: float,
    source_name: str,
) -> Optional[Dict[str, Any]]:
    """Return {'text': str, 'midi_bytes': bytes} or None if stem missing or silent."""
    if not piano_path.exists():
        return None

    notes = transcribe(piano_path)
    if not notes:
        return None

    return {
        "text": _notes_to_text(notes, bars=bars, tempo=tempo),
        "midi_bytes": _notes_to_midi(notes, tempo=tempo),
    }
