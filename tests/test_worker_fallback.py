"""Test that worker.run_job falls back gracefully when SynthTab or BTC fail."""
from pathlib import Path
from unittest.mock import MagicMock, patch
import numpy as np
import pytest


def _make_job(tmp_path):
    job = MagicMock()
    job.work_dir = tmp_path
    job.total_steps = 10
    job.step = 0
    job.step_label = ""
    job.status = "queued"
    job.error = ""
    return job


def _librosa_mock():
    """MagicMock for the entire librosa import in api.worker."""
    m = MagicMock()
    m.load.return_value = (np.zeros(22050), 22050)
    m.effects.hpss.return_value = (np.zeros(22050), np.zeros(22050))
    m.feature.chroma_cens.return_value = np.zeros((12, 10))
    m.frames_to_time.return_value = np.zeros(10)
    return m


_BASE_PARAMS = {
    "youtube_url": None,
    "tuning": "Standard EADGBE",
    "key": "auto",
    "multi_guitar": False,
    "bass_tab": False,
    "vocal_tab": False,
    "drum_summary": False,
    "keys_tab": False,
    "lyrics_raw": None,
}


def test_synthtab_failure_falls_back_to_basic_pitch(tmp_path):
    """When SynthTab raises, worker uses basic-pitch and job still completes."""
    from pipeline.transcription import Note
    from pipeline.chord_detection import ChordSegment

    fake_notes = [Note(start=0.0, end=0.5, pitch=60, velocity=0.8)]
    fake_bars = [ChordSegment(bar_index=0, start=0.0, end=2.0, label="Em")]

    with (
        patch("api.worker.job_store.get_job") as mock_get_job,
        patch("api.worker.separation.separate", return_value=(
            tmp_path / "harm.wav", tmp_path / "bass.wav", tmp_path / "guitar.wav"
        )),
        patch("api.worker.transcription_synthtab.transcribe",
              side_effect=RuntimeError("model missing")),
        patch("api.worker.transcription.transcribe", return_value=fake_notes),
        patch("api.worker.librosa", _librosa_mock()),
        patch("api.worker.key_detection.detect_key", return_value=MagicMock()),
        patch("api.worker.chord_detection.detect_chords",
              return_value=(fake_bars, 120.0)),
        patch("api.worker.chord_detection_btc.detect_chords_btc",
              return_value=(fake_bars, fake_bars)),
        patch("api.worker.fretboard.map_notes_to_fretboard", return_value=[]),
        patch("api.worker.tab_render.render_tab", return_value=""),
        patch("api.worker.export_pdf"),
        patch("api.worker.export_midi"),
        patch("api.worker.tuning_mod.find_tuning",
              return_value=MagicMock(name="Standard EADGBE")),
        patch("api.worker.tuning_mod.suggest_alternate_tuning", return_value=None),
    ):
        job = _make_job(tmp_path)
        mock_get_job.return_value = job

        from api import worker
        worker.run_job("test-job", {"audio_path": tmp_path / "audio.wav", **_BASE_PARAMS})

        assert job.status == "done"
        assert "fallback" in job.step_label.lower()


def test_btc_failure_falls_back_to_legacy_chords(tmp_path):
    """When BTC raises, worker uses legacy chord detection and job still completes."""
    from pipeline.transcription import Note
    from pipeline.chord_detection import ChordSegment

    fake_notes = [Note(start=0.0, end=0.5, pitch=60, velocity=0.8)]
    fake_bars = [ChordSegment(bar_index=0, start=0.0, end=2.0, label="Em")]

    with (
        patch("api.worker.job_store.get_job") as mock_get_job,
        patch("api.worker.separation.separate", return_value=(
            tmp_path / "harm.wav", tmp_path / "bass.wav", tmp_path / "guitar.wav"
        )),
        patch("api.worker.transcription_synthtab.transcribe", return_value=fake_notes),
        patch("api.worker.librosa", _librosa_mock()),
        patch("api.worker.key_detection.detect_key", return_value=MagicMock()),
        patch("api.worker.chord_detection.detect_chords",
              return_value=(fake_bars, 120.0)),
        patch("api.worker.chord_detection_btc.detect_chords_btc",
              side_effect=RuntimeError("GPU OOM")),
        patch("api.worker.fretboard.map_notes_to_fretboard", return_value=[]),
        patch("api.worker.tab_render.render_tab", return_value=""),
        patch("api.worker.export_pdf"),
        patch("api.worker.export_midi"),
        patch("api.worker.tuning_mod.find_tuning",
              return_value=MagicMock(name="Standard EADGBE")),
        patch("api.worker.tuning_mod.suggest_alternate_tuning", return_value=None),
    ):
        job = _make_job(tmp_path)
        mock_get_job.return_value = job

        from api import worker
        worker.run_job("test-job", {"audio_path": tmp_path / "audio.wav", **_BASE_PARAMS})

        assert job.status == "done"
        assert "fallback" in job.step_label.lower()
        assert job.results["bars"][0]["label"] == "Em"
