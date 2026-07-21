import numpy as np

from pipeline.chord_detection import _bass_root_pitch_class


def test_bass_root_pitch_class_detects_a_clear_single_note():
    # All energy in bin 9 (A) -- an unambiguous, sustained bass note
    vec = np.zeros(12)
    vec[9] = 1.0
    assert _bass_root_pitch_class(vec) == 9


def test_bass_root_pitch_class_returns_none_for_a_near_uniform_vector():
    # Energy spread evenly across all 12 bins -- no single note dominates
    vec = np.full(12, 1.0 / 12)
    assert _bass_root_pitch_class(vec) is None


def test_bass_root_pitch_class_returns_none_for_silence():
    vec = np.zeros(12)
    assert _bass_root_pitch_class(vec) is None
