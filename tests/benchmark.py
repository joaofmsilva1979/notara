#!/usr/bin/env python3
"""Benchmark: compare legacy vs BTC chord detection.

Usage:
    python -m tests.benchmark /path/to/song.wav [/path/to/song2.wav ...]

Each WAV needs a companion `<name>.chords.txt` with one chord label per line
(one per bar). Lines without a companion .chords.txt still run — accuracy shows as "N/A".

Output: a table comparing legacy vs BTC chord accuracy per file.
"""
from __future__ import annotations

import math
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import librosa

from pipeline import chord_detection, key_detection, separation, transcription
from pipeline import chord_detection_btc


def _load_expected(wav_path: Path) -> list[str]:
    p = wav_path.with_suffix(".chords.txt")
    if not p.exists():
        return []
    return [l.strip() for l in p.read_text().splitlines() if l.strip()]


def _accuracy(detected: list[str], expected: list[str]) -> float:
    if not expected:
        return float("nan")
    n = min(len(detected), len(expected))
    return sum(d == e for d, e in zip(detected[:n], expected[:n])) / len(expected)


def _fmt(v: float) -> str:
    return f"{v:.1%}" if not math.isnan(v) else "N/A"


def _run_file(wav_path: Path) -> dict:
    print(f"  Processing: {wav_path.name} ...", end=" ", flush=True)
    expected = _load_expected(wav_path)
    work = Path(tempfile.mkdtemp(prefix="notara_bench_"))
    try:
        harmonic, bass_path, guitar_stem = separation.separate(wav_path, work)
        y, sr = librosa.load(str(harmonic), sr=None, mono=True)
        bass_y, bass_sr = librosa.load(str(bass_path), sr=None, mono=True)
        key_est = key_detection.detect_key(y, sr)

        bars_legacy, tempo = chord_detection.detect_chords(y, sr, bass_y, bass_sr, key_est)
        labels_legacy = [b.label for b in bars_legacy]

        try:
            bars_btc, _ = chord_detection_btc.detect_chords_btc(wav_path, bars_legacy)
            labels_btc = [b.label for b in bars_btc]
            btc_ok = True
        except Exception as exc:
            labels_btc = []
            btc_ok = False
            print(f"[BTC failed: {exc}]", end=" ")

        print("done")
        return {
            "file": wav_path.name,
            "tempo": round(tempo, 1),
            "bars": len(bars_legacy),
            "legacy_acc": _accuracy(labels_legacy, expected),
            "btc_acc": _accuracy(labels_btc, expected) if btc_ok else float("nan"),
        }
    finally:
        shutil.rmtree(work, ignore_errors=True)


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    results = [_run_file(Path(p)) for p in sys.argv[1:]]

    print()
    print("=" * 72)
    print(f"{'File':<32} {'Tempo':>6} {'Bars':>5} {'Legacy acc':>12} {'BTC acc':>10}")
    print("-" * 72)
    for r in results:
        print(f"{r['file']:<32} {r['tempo']:>6.1f} {r['bars']:>5} "
              f"{_fmt(r['legacy_acc']):>12} {_fmt(r['btc_acc']):>10}")
    print("=" * 72)

    btc_scores = [r["btc_acc"] for r in results if not math.isnan(r["btc_acc"])]
    leg_scores = [r["legacy_acc"] for r in results if not math.isnan(r["legacy_acc"])]
    if btc_scores and leg_scores:
        avg_btc = sum(btc_scores) / len(btc_scores)
        avg_leg = sum(leg_scores) / len(leg_scores)
        diff = avg_btc - avg_leg
        print()
        if diff > 0.05:
            print(f"RECOMMENDATION: BTC is better by {diff:.1%} → keep as default")
        elif diff < -0.05:
            print(f"RECOMMENDATION: Legacy is better by {-diff:.1%} → revert BTC default")
        else:
            print(f"RECOMMENDATION: No significant difference ({diff:+.1%}) → keep BTC (richer vocab)")


if __name__ == "__main__":
    main()
