import sys

import pytest

from main import parse_args
from pipeline.tuning import BASS_STANDARD_EADG


def parse_args_for_test(argv):
    return parse_args(argv)


def test_tuning_flag_defaults_to_standard(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["main.py", "song.wav"])
    args = parse_args()
    assert args.tuning == "Standard EADGBE"


def test_tuning_flag_accepts_known_preset(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["main.py", "song.wav", "--tuning", "Drop D"])
    args = parse_args()
    assert args.tuning == "Drop D"


def test_tuning_flag_rejects_unknown_preset(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["main.py", "song.wav", "--tuning", "Nope"])
    with pytest.raises(SystemExit):
        parse_args()


def test_multi_guitar_flag_defaults_to_false(tmp_path):
    wav = tmp_path / "s.wav"
    wav.touch()
    args = parse_args_for_test([str(wav)])
    assert args.multi_guitar is False


def test_multi_guitar_flag_can_be_set(tmp_path):
    wav = tmp_path / "s.wav"
    wav.touch()
    args = parse_args_for_test([str(wav), "--multi-guitar"])
    assert args.multi_guitar is True


def test_bass_tuning_defaults_to_standard(tmp_path):
    wav = tmp_path / "s.wav"
    wav.touch()
    args = parse_args_for_test([str(wav)])
    assert args.bass_tuning == BASS_STANDARD_EADG


def test_bass_tuning_can_be_set(tmp_path):
    wav = tmp_path / "s.wav"
    wav.touch()
    from pipeline.tuning import BASS_DROP_D
    args = parse_args_for_test([str(wav), "--bass-tuning", BASS_DROP_D])
    assert args.bass_tuning == BASS_DROP_D
