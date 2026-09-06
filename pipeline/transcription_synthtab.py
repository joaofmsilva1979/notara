"""Guitar transcription using SynthTab's TabCNN model.

Replaces basic-pitch for guitar stems — outputs per-string, per-fret predictions,
giving accurate chord voicings and picking patterns across all 6 strings.

Output shape from model: (T, 6, 1) int64 where values are:
  -1 = string muted / not played
   0 = fret 0 (open string)
   1 = fret 1, ..., 19 = fret 19
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Optional

import numpy as np
import torch

_SYNTHTAB_DIR = Path(__file__).parent / "synthtab" / "demo_embedding"
if str(_SYNTHTAB_DIR) not in sys.path:
    sys.path.insert(0, str(_SYNTHTAB_DIR))

from amt_tools import tools
from amt_tools.features import CQT

from .transcription import Note

_MODEL_PATH = _SYNTHTAB_DIR / "pretrained_models" / "SynthTab-Pretrained.pt"

# Standard EADGBE open-string MIDI pitches (model index 0=low E … 5=high E)
_OPEN_STRING_MIDI = [40, 45, 50, 55, 59, 64]

_SAMPLE_RATE = 22050
_HOP_LENGTH = 512
_N_BINS = 192
_BINS_PER_OCTAVE = 24

_MIN_NOTE_SEC = 0.08   # drop notes shorter than 80 ms — avoids fret-flicker artifacts
_MIN_VELOCITY = 0.5    # SynthTab has no velocity; use a fixed value

_model = None
_cqt: Optional[CQT] = None


def _load() -> None:
    global _model, _cqt
    if _model is not None:
        return

    device = torch.device("cpu")
    m = torch.load(str(_MODEL_PATH), map_location=device, weights_only=False)
    m.eval()
    m.device = device
    _model = m

    _cqt = CQT(
        sample_rate=_SAMPLE_RATE,
        hop_length=_HOP_LENGTH,
        n_bins=_N_BINS,
        bins_per_octave=_BINS_PER_OCTAVE,
    )


def _tab_to_notes(tab: np.ndarray) -> List[Note]:
    """Convert (T, 6) fret array to Note events.

    Merges consecutive frames of the same fret on the same string into one note.
    """
    T, n_strings = tab.shape
    sec_per_frame = _HOP_LENGTH / _SAMPLE_RATE
    notes: List[Note] = []

    for s in range(n_strings):
        open_midi = _OPEN_STRING_MIDI[s]
        prev_fret = -1
        note_start = 0

        for f in range(T):
            fret = int(tab[f, s])
            if fret != prev_fret:
                if prev_fret >= 0:
                    start_t = note_start * sec_per_frame
                    end_t = f * sec_per_frame
                    if end_t - start_t >= _MIN_NOTE_SEC:
                        notes.append(Note(
                            start=start_t, end=end_t,
                            pitch=open_midi + prev_fret,
                            velocity=_MIN_VELOCITY,
                        ))
                if fret >= 0:
                    note_start = f
                prev_fret = fret

        if prev_fret >= 0:
            start_t = note_start * sec_per_frame
            end_t = T * sec_per_frame
            if end_t - start_t >= _MIN_NOTE_SEC:
                notes.append(Note(
                    start=start_t, end=end_t,
                    pitch=open_midi + prev_fret,
                    velocity=_MIN_VELOCITY,
                ))

    notes.sort(key=lambda n: n.start)
    return notes


def transcribe(audio_path: Path) -> List[Note]:
    """Transcribe guitar audio using SynthTab TabCNN.

    Args:
        audio_path: path to audio file (WAV or any librosa-readable format)

    Returns:
        Note events sorted by start time.
        Assumes standard EADGBE tuning — if the recording uses an alternate
        tuning the MIDI pitches will be relative to that assumption.
    """
    import librosa

    _load()

    y, _ = librosa.load(str(audio_path), sr=_SAMPLE_RATE, mono=True)
    feats = _cqt.process_audio(y)  # (1, 192, T)

    batch = {tools.KEY_FEATS: feats}
    batch = _model.pre_proc(batch)

    with torch.no_grad():
        output = _model(batch[tools.KEY_FEATS])

    batch[tools.KEY_OUTPUT] = output
    result = _model.post_proc(batch)

    # (T, 6, 1) → (T, 6)
    tab = result[tools.KEY_TABLATURE].squeeze(-1).cpu().numpy()

    return _tab_to_notes(tab)
