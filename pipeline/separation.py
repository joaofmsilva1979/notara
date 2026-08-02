"""Step 1: source separation with Demucs.

Uses the 6-stem model (htdemucs_6s), which has a dedicated "guitar" stem
in addition to drums/bass/vocals/piano/other. We combine guitar + other
into a single "harmonic" mix (for transcription and key detection) and
also return the separated bass stem on its own (used by chord_detection.py
to constrain the chord root). Drums/vocals/piano are still discarded.

Known limitation: everything downstream depends on how well Demucs isolates
guitar content. Bleed from drums/vocals into the guitar stem (or guitar
content leaking into "other"/"piano") will directly corrupt note detection.
Distorted/heavily effected electric guitar separates worse than clean
acoustic or electric guitar.

Multi-guitar note: separate_guitars() splits the guitar stem's stereo
channels into left (guitar 1) and right (guitar 2) mono files. This works
well for recordings where two guitars are panned to opposite sides (common
in rock/pop). For mono recordings or songs where guitars share the same
pan position, guitar2_path will be None (mono source) or effectively
identical to guitar1_path (same-pan stereo). In those cases the output
is the same as single-guitar mode.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Optional, Tuple

import numpy as np
import soundfile as sf

DEMUCS_MODEL = "htdemucs_6s"
HARMONIC_STEMS = ("guitar", "other")


def _run_demucs(audio_path: Path, out_dir: Path, device: str) -> Path:
    """Run Demucs and return the stem directory for the track."""
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable, "-m", "demucs",
        "-n", DEMUCS_MODEL,
        "-d", device,
        "-o", str(out_dir),
        str(audio_path),
    ]
    subprocess.run(cmd, check=True)
    stem_dir = out_dir / DEMUCS_MODEL / audio_path.stem
    if not stem_dir.exists():
        raise FileNotFoundError(f"Demucs did not produce expected output at {stem_dir}")
    return stem_dir


def _combine_stems(stem_dir: Path, work_dir: Path) -> Path:
    signals = []
    sr = None
    for stem_name in HARMONIC_STEMS:
        stem_path = stem_dir / f"{stem_name}.wav"
        if not stem_path.exists():
            continue
        y, file_sr = sf.read(stem_path, always_2d=False)
        if sr is None:
            sr = file_sr
        elif file_sr != sr:
            raise ValueError(f"Sample rate mismatch between stems: {file_sr} vs {sr}")
        signals.append(y if y.ndim == 1 else y.mean(axis=1))

    if not signals:
        raise FileNotFoundError(f"No harmonic stems found in {stem_dir}")

    max_len = max(len(s) for s in signals)
    mix = np.zeros(max_len, dtype=np.float64)
    for s in signals:
        mix[: len(s)] += s

    peak = np.max(np.abs(mix))
    if peak > 1.0:
        mix = mix / peak * 0.98

    harmonic_path = work_dir / "harmonic_mix.wav"
    sf.write(harmonic_path, mix, sr)
    return harmonic_path


def separate(audio_path: Path, work_dir: Path, device: str = "cpu") -> tuple[Path, Path]:
    """Run Demucs and return (harmonic_mix_path, bass_stem_path)."""
    out_dir = work_dir / "stems"
    stem_dir = _run_demucs(audio_path, out_dir, device)

    bass_stem_path = stem_dir / "bass.wav"
    if not bass_stem_path.exists():
        raise FileNotFoundError(f"Demucs did not produce a bass stem at {bass_stem_path}")

    harmonic_path = _combine_stems(stem_dir, work_dir)
    return harmonic_path, bass_stem_path


def separate_guitars(
    audio_path: Path, work_dir: Path, device: str = "cpu"
) -> Tuple[Path, Optional[Path], Path, Path]:
    """Run Demucs and return (guitar1_path, guitar2_path_or_None, bass_path, harmonic_mix_path).

    guitar1 = left channel of the Demucs guitar stem (mono WAV).
    guitar2 = right channel of the Demucs guitar stem (mono WAV), or None if
              the guitar stem is mono (single-channel source).
    bass_path = raw Demucs bass stem (stereo, used as-is for bass transcription).
    harmonic_mix = guitar + other combined mono mix (for key/chord detection,
                   same as what separate() returns).
    """
    out_dir = work_dir / "stems"
    stem_dir = _run_demucs(audio_path, out_dir, device)

    bass_stem_path = stem_dir / "bass.wav"
    if not bass_stem_path.exists():
        raise FileNotFoundError(f"Demucs did not produce a bass stem at {bass_stem_path}")

    guitar_stem_path = stem_dir / "guitar.wav"
    if not guitar_stem_path.exists():
        raise FileNotFoundError(f"Demucs did not produce a guitar stem at {guitar_stem_path}")

    harmonic_path = _combine_stems(stem_dir, work_dir)

    guitar_data, guitar_sr = sf.read(str(guitar_stem_path))
    if guitar_data.ndim == 1 or guitar_data.shape[1] < 2:
        guitar1_path = work_dir / "guitar1.wav"
        mono = guitar_data if guitar_data.ndim == 1 else guitar_data[:, 0]
        sf.write(str(guitar1_path), mono, guitar_sr)
        return guitar1_path, None, bass_stem_path, harmonic_path

    left = guitar_data[:, 0]
    right = guitar_data[:, 1]
    guitar1_path = work_dir / "guitar1.wav"
    guitar2_path = work_dir / "guitar2.wav"
    sf.write(str(guitar1_path), left, guitar_sr)
    sf.write(str(guitar2_path), right, guitar_sr)
    return guitar1_path, guitar2_path, bass_stem_path, harmonic_path
