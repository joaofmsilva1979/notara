"""Step 3: key detection via chroma profile + Krumhansl-Schmuckler.

We compute a chromagram over the whole harmonic mix, average it into a
single 12-bin pitch-class profile, then correlate that profile (at each of
the 12 rotations) against the empirically-derived Krumhansl-Kessler major
and minor key profiles. The rotation/mode with the highest Pearson
correlation wins.

Known limitation: this is a global, whole-track estimate. Songs that
modulate key, or that are modal/ambiguous (e.g. lots of parallel major/minor
color, or no clear tonic), can get a "best fit" key that doesn't match a
human's judgment for the whole song.
"""
from __future__ import annotations

from dataclasses import dataclass

import librosa
import numpy as np

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# Krumhansl-Kessler key profiles
MAJOR_PROFILE = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
MINOR_PROFILE = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])


@dataclass
class KeyEstimate:
    tonic: str
    mode: str  # "major" or "minor"
    correlation: float

    def __str__(self) -> str:
        return f"{self.tonic} {self.mode}"


def _correlate(profile: np.ndarray, template: np.ndarray) -> float:
    p = profile - profile.mean()
    t = template - template.mean()
    denom = np.linalg.norm(p) * np.linalg.norm(t)
    if denom == 0:
        return 0.0
    return float(np.dot(p, t) / denom)


def detect_key(y: np.ndarray, sr: int) -> KeyEstimate:
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
    profile = chroma.mean(axis=1)  # average pitch-class energy over full track

    best = None
    for mode_name, template in (("major", MAJOR_PROFILE), ("minor", MINOR_PROFILE)):
        for rotation in range(12):
            rotated = np.roll(template, rotation)
            score = _correlate(profile, rotated)
            if best is None or score > best.correlation:
                best = KeyEstimate(tonic=NOTE_NAMES[rotation], mode=mode_name, correlation=score)

    assert best is not None
    return best
