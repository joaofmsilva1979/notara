"""Optional step: split the single transcribed guitar part into two "voices"
(e.g. a rhythm/lower tab and a lead/upper tab).

IMPORTANT limitation: Demucs only isolates ONE guitar bus (the "guitar" stem
from htdemucs_6s). If the original mix has two real guitars, they are NOT
separated as distinct sources -- they're both smashed into that one stem and
transcribed together. This function does NOT detect "two guitars"; it just
splits the combined note stream by which strings the fretboard-mapping step
put them on (treble strings G/B/e vs bass strings E/A/D), as a readability
hack for dense passages. Treat "voice 1" / "voice 2" as "upper register" /
"lower register" of the same transcription, not as two independently
verified guitar parts.
"""
from __future__ import annotations

from typing import List, Tuple

from .fretboard import FrettedNote

TREBLE_STRINGS = {3, 4, 5}  # G, B, e
BASS_STRINGS = {0, 1, 2}    # E, A, D


def split_voices(notes: List[FrettedNote]) -> Tuple[List[FrettedNote], List[FrettedNote]]:
    voice_treble = [n for n in notes if n.string in TREBLE_STRINGS]
    voice_bass = [n for n in notes if n.string in BASS_STRINGS]
    return voice_treble, voice_bass
