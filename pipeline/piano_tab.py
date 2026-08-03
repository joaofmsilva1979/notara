"""Piano/keyboard tab rendering using the Demucs piano stem.

Transcribes the piano stem via Basic-Pitch and renders a simple
text-based representation of the keyboard part. Returns None if the
piano stem is absent or too quiet to contain meaningful content.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional


def render_piano_tab(
    piano_path: Path,
    bars: int,
    key_est: str,
    tempo: float,
    source_name: str,
) -> Optional[Dict[str, Any]]:
    """Transcribe the piano stem and return a text representation + MIDI bytes.

    Returns a dict with keys ``text`` (str) and ``midi_bytes`` (bytes | None),
    or None if the stem does not exist or is silent.
    """
    if not piano_path.exists():
        return None

    try:
        import librosa  # noqa: PLC0415
        import numpy as np  # noqa: PLC0415

        y, sr = librosa.load(str(piano_path), sr=None, mono=True)
        rms = float(np.sqrt(np.mean(y ** 2)))
        if rms < 1e-4:
            return None

        # Placeholder: emit a minimal text representation.
        # A full implementation would run Basic-Pitch on `piano_path` and
        # convert the MIDI result to a staff-style ASCII render.
        header = (
            f"=== Keys / Keyboard ===\n"
            f"Source : {source_name}\n"
            f"Key    : {key_est}\n"
            f"Tempo  : {tempo:.1f} BPM\n"
            f"Bars   : {bars}\n"
            "──────────────────────\n"
            "[Piano stem detected — full transcription not yet implemented]\n"
        )
        return {"text": header, "midi_bytes": None}

    except Exception:  # noqa: BLE001
        return None
