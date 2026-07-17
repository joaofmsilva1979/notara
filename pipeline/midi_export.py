"""Optional step: export the quantized, fretted notes as a standard MIDI file
using mido.

This is deliberately separate from the raw MIDI that basic-pitch can also
produce: this file reflects the notes AFTER fretboard mapping and bar
quantization, i.e. exactly what ended up in the ASCII tab, which is useful
for double-checking the tab against the transcription by ear.
"""
from __future__ import annotations

from pathlib import Path
from typing import List

import mido

from .fretboard import FrettedNote

TICKS_PER_BEAT = 480


def export_midi(path: Path, notes: List[FrettedNote], tempo_bpm: float) -> None:
    midi = mido.MidiFile(ticks_per_beat=TICKS_PER_BEAT)
    track = mido.MidiTrack()
    midi.tracks.append(track)
    track.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(tempo_bpm)))

    tempo_us = mido.bpm2tempo(tempo_bpm)
    events = []  # (tick, is_note_on, pitch)
    for note in notes:
        start_tick = round(mido.second2tick(note.start, TICKS_PER_BEAT, tempo_us))
        end_tick = round(mido.second2tick(note.end, TICKS_PER_BEAT, tempo_us))
        end_tick = max(end_tick, start_tick + 1)
        events.append((start_tick, 1, note.pitch))
        events.append((end_tick, 0, note.pitch))

    events.sort(key=lambda e: (e[0], e[1]))  # note_off before note_on at same tick

    last_tick = 0
    for tick, is_on, pitch in events:
        delta = max(0, tick - last_tick)
        if is_on:
            track.append(mido.Message("note_on", note=pitch, velocity=80, time=delta))
        else:
            track.append(mido.Message("note_off", note=pitch, velocity=0, time=delta))
        last_tick = tick

    midi.save(str(path))
