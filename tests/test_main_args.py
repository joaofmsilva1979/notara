import sys

import pytest

from main import parse_args


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
