# tests/test_drum_summary.py
import numpy as np
import pytest
from pipeline import drum_summary


def test_classify_onset_kick():
    sr = 22050
    t = np.linspace(0, 0.05, int(sr * 0.05))
    # Synthesise a 100 Hz sine (kick-band)
    y = np.sin(2 * np.pi * 100 * t).astype(np.float32)
    result = drum_summary._classify_onset(y, sr, 0)
    assert result == "K"


def test_classify_onset_hihat():
    sr = 22050
    t = np.linspace(0, 0.05, int(sr * 0.05))
    # Synthesise a 10000 Hz sine (hi-hat band)
    y = np.sin(2 * np.pi * 10000 * t).astype(np.float32)
    result = drum_summary._classify_onset(y, sr, 0)
    assert result == "H"


def test_build_grid_places_onsets():
    onsets = np.array([0.0, 0.5])  # beat 1 and beat 1+
    labels = ["K", "S"]
    grid = drum_summary._build_grid(onsets, labels, tempo=120.0, n_bars=1)
    assert "●" in grid["K"][0]
    assert "●" in grid["S"][0]


def test_ascii_pattern_has_three_rows():
    onsets = np.array([0.0, 0.25, 0.5])
    labels = ["K", "H", "S"]
    grid = drum_summary._build_grid(onsets, labels, tempo=120.0, n_bars=1)
    pattern = drum_summary._ascii_pattern(grid)
    assert "K:" in pattern
    assert "S:" in pattern
    assert "HH:" in pattern


def test_summarize_drums_returns_string(tmp_path):
    import soundfile as sf
    sr = 22050
    duration = 4.0
    # Synthesise a simple kick pattern (100 Hz bursts)
    y = np.zeros(int(sr * duration), dtype=np.float32)
    for beat in [0.0, 0.5, 1.0, 1.5]:
        start = int(beat * sr)
        end = min(start + int(0.05 * sr), len(y))
        t = np.linspace(0, 0.05, end - start)
        y[start:end] = np.sin(2 * np.pi * 100 * t).astype(np.float32)
    drum_path = tmp_path / "drums.wav"
    sf.write(str(drum_path), y, sr)
    result = drum_summary.summarize_drums(drum_path, tempo=120.0)
    assert isinstance(result, str)
    assert "BPM" in result
