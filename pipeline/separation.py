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
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

DEMUCS_MODEL = "htdemucs_6s"
HARMONIC_STEMS = ("guitar", "other")


def separate(audio_path: Path, work_dir: Path, device: str = "cpu") -> tuple[Path, Path]:
    """Run Demucs and return (harmonic_mix_path, bass_stem_path)."""
    out_dir = work_dir / "stems"
    out_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable, "-m", "demucs",
        "-n", DEMUCS_MODEL,
        "-d", device,
        "-o", str(out_dir),
        str(audio_path),
    ]
    subprocess.run(cmd, check=True)

    track_name = audio_path.stem
    stem_dir = out_dir / DEMUCS_MODEL / track_name
    if not stem_dir.exists():
        raise FileNotFoundError(f"Demucs did not produce expected output at {stem_dir}")

    bass_stem_path = stem_dir / "bass.wav"
    if not bass_stem_path.exists():
        raise FileNotFoundError(f"Demucs did not produce a bass stem at {bass_stem_path}")

    harmonic_path = _combine_stems(stem_dir, work_dir)
    return harmonic_path, bass_stem_path


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
        signals.append(y)

    if not signals:
        raise FileNotFoundError(f"No harmonic stems found in {stem_dir}")

    max_len = max(len(s) for s in signals)
    mix = np.zeros((max_len,) + signals[0].shape[1:], dtype=np.float64)
    for s in signals:
        mix[: len(s)] += s

    peak = np.max(np.abs(mix))
    if peak > 1.0:
        mix = mix / peak * 0.98

    harmonic_path = work_dir / "harmonic_mix.wav"
    sf.write(harmonic_path, mix, sr)
    return harmonic_path
