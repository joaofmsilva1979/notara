"""Unit tests for pipeline/chord_detection_btc.py.

All tests mock the BTC model — no model weights are loaded.
"""
from unittest.mock import MagicMock, patch
import numpy as np
import pytest
from pipeline.chord_detection import ChordSegment
from pipeline import chord_detection_btc


@pytest.fixture(autouse=True)
def _mock_btc(monkeypatch):
    """Inject a pre-loaded model so _load_model() is a no-op."""
    mock_model = MagicMock()
    mock_model.parameters.return_value = iter([MagicMock(device="cpu")])

    import torch
    fake_logits = torch.zeros(1, 4, 170)
    mock_model.self_attn_layers.return_value = (fake_logits, None)
    mock_model.output_layer.output_projection.return_value = fake_logits

    monkeypatch.setattr(chord_detection_btc, "_model", mock_model)
    monkeypatch.setattr(chord_detection_btc, "_mean", np.float32(0.0))
    monkeypatch.setattr(chord_detection_btc, "_std", np.float32(1.0))
    monkeypatch.setattr(chord_detection_btc, "_idx_to_chord", {
        **{i: "C:maj" for i in range(170)},
        168: "N",
        169: "X",
    })
    monkeypatch.setattr(chord_detection_btc, "_config", MagicMock(
        model={"timestep": 4, "num_chords": 170}
    ))


# ── _btc_to_notara ────────────────────────────────────────────────────────────

def test_btc_to_notara_major():
    assert chord_detection_btc._btc_to_notara("C:maj") == "C"

def test_btc_to_notara_minor():
    assert chord_detection_btc._btc_to_notara("A:min") == "Am"

def test_btc_to_notara_dominant7():
    assert chord_detection_btc._btc_to_notara("G:7") == "G7"

def test_btc_to_notara_sus4():
    assert chord_detection_btc._btc_to_notara("D:sus4") == "Dsus4"

def test_btc_to_notara_nc():
    assert chord_detection_btc._btc_to_notara("N") == "N.C."
    assert chord_detection_btc._btc_to_notara("X") == "N.C."

def test_btc_to_notara_plain_root():
    # No colon — treat as major root
    assert chord_detection_btc._btc_to_notara("Em") == "Em"


# ── _bass_forced_root ─────────────────────────────────────────────────────────

def test_bass_forced_root_strong_signal():
    chroma = np.zeros(12)
    chroma[0] = 1.0  # C dominates clearly
    assert chord_detection_btc._bass_forced_root(chroma) == 0

def test_bass_forced_root_weak_signal():
    # Uniform distribution — no single root dominates above BASS_CLARITY_THRESHOLD
    chroma = np.ones(12) / 12.0
    assert chord_detection_btc._bass_forced_root(chroma) is None

def test_bass_forced_root_zero_total():
    assert chord_detection_btc._bass_forced_root(np.zeros(12)) is None


# ── _apply_bass_crosscheck ────────────────────────────────────────────────────

def test_bass_crosscheck_corrects_root():
    # BTC says "G" but bass strongly says C (index 0)
    chroma = np.zeros(12)
    chroma[0] = 1.0
    result = chord_detection_btc._apply_bass_crosscheck("G", chroma)
    assert result.startswith("C")

def test_bass_crosscheck_agrees_keeps_label():
    # BTC says "C", bass also says C
    chroma = np.zeros(12)
    chroma[0] = 1.0
    assert chord_detection_btc._apply_bass_crosscheck("C", chroma) == "C"

def test_bass_crosscheck_nc_unchanged():
    chroma = np.zeros(12)
    chroma[0] = 1.0
    assert chord_detection_btc._apply_bass_crosscheck("N.C.", chroma) == "N.C."


# ── _group_frame_events ───────────────────────────────────────────────────────

def test_group_frame_events_merges_short_event():
    idx_to_chord = {0: "C:maj", 1: "A:min"}
    # One brief "A:min" frame (0.1 s) surrounded by "C:maj" — below MIN_CHORD_DURATION
    preds = [0, 0, 0, 0, 1, 0, 0, 0]
    events = chord_detection_btc._group_frame_events(preds, 0.1, idx_to_chord, 0.8)
    assert all(e.label != "Am" for e in events)

def test_group_frame_events_keeps_long_event():
    idx_to_chord = {0: "C:maj", 1: "A:min"}
    # 4 frames of "A:min" at 0.1 s/frame = 0.4 s → above MIN_CHORD_DURATION (0.2 s)
    preds = [0, 0, 1, 1, 1, 1, 0, 0]
    events = chord_detection_btc._group_frame_events(preds, 0.1, idx_to_chord, 0.8)
    assert any(e.label == "Am" for e in events)

def test_group_frame_events_empty():
    assert chord_detection_btc._group_frame_events([], 0.1, {}, 1.0) == []


# ── _viterbi_smooth ───────────────────────────────────────────────────────────

def test_viterbi_smooth_returns_same_length():
    log_probs = np.log(np.ones((10, 5)) / 5)
    path = chord_detection_btc._viterbi_smooth(log_probs)
    assert len(path) == 10

def test_viterbi_smooth_strong_signal():
    # Frame 0-4: class 0 dominant; frame 5-9: class 2 dominant
    lp = np.full((10, 5), -10.0)
    lp[:5, 0] = 0.0
    lp[5:, 2] = 0.0
    path = chord_detection_btc._viterbi_smooth(lp, self_loop=0.5)
    assert path[0] == 0
    assert path[9] == 2
