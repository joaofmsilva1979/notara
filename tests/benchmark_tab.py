"""Tab accuracy benchmark on GuitarSet (string + fret ground truth).

GuitarSet: 360 solo-guitar recordings, standard tuning, every note annotated
with its string and fret (https://zenodo.org/records/3371780).

Two levels, run separately:

  fingering   ground-truth notes → map_notes_to_fretboard → % notes on the
              right string/fret. Isolates the placement algorithm. Fast, no ML.
  e2e         audio → transcriber → placement → compared with ground truth:
              note F1 (pitch + onset within 50 ms) and tab accuracy (right
              string/fret among matched notes). Slow.

Usage:
  python tests/benchmark_tab.py fingering --root ~/datasets/GuitarSet
  python tests/benchmark_tab.py e2e --root ~/datasets/GuitarSet --limit 30
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Callable, Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.fretboard import map_notes_to_fretboard_dp, map_notes_to_fretboard_greedy as map_notes_to_fretboard  # noqa: E402
from pipeline.transcription import Note  # noqa: E402

OPEN = [40, 45, 50, 55, 59, 64]
ONSET_TOL = 0.05

GT = Tuple[float, float, int, int, int]  # start, end, pitch, string, fret


def load_jams(path: Path) -> List[GT]:
    data = json.loads(path.read_text())
    out: List[GT] = []
    for ann in data["annotations"]:
        if ann["namespace"] != "note_midi":
            continue
        s = int(ann["annotation_metadata"]["data_source"])
        for ev in ann["data"]:
            pitch = int(round(ev["value"]))
            out.append((ev["time"], ev["time"] + ev["duration"], pitch, s, pitch - OPEN[s]))
    out.sort()
    return out


def tracks(root: Path, limit: int | None) -> List[Path]:
    files = sorted((root / "annotation").glob("*.jams"))
    if limit:
        step = max(1, len(files) // limit)  # spread over players and styles
        files = files[::step][:limit]
    return files


MAPPERS = {"greedy": map_notes_to_fretboard, "dp": map_notes_to_fretboard_dp}


def fingering(root: Path, limit: int | None, mapper: str = "dp", players: str = "") -> None:
    ok = total = 0
    for jp in tracks(root, limit):
        if players and jp.name[:2] not in players.split(","):
            continue
        gt = load_jams(jp)
        notes = [Note(start=a, end=b, pitch=p, velocity=1.0) for a, b, p, _, _ in gt]
        placed = MAPPERS[mapper](notes)
        truth: Dict[Tuple[float, int], Tuple[int, int]] = {(round(a, 4), p): (s, f) for a, _, p, s, f in gt}
        for fn in placed:
            if truth.get((round(fn.start, 4), fn.pitch)) == (fn.string, fn.fret):
                ok += 1
        total += len(gt)
    print(f"fingering [{mapper}{' players ' + players if players else ''}]: {ok}/{total} notes on the right string+fret = {100 * ok / total:.1f}%")


def _match(pred, gt: List[GT]):
    """Greedy one-to-one match on pitch + onset tolerance."""
    used = set()
    pairs = []
    for fn in sorted(pred, key=lambda n: n.start):
        best, best_d = None, ONSET_TOL
        for i, (a, _, p, _, _) in enumerate(gt):
            if i in used or p != fn.pitch:
                continue
            d = abs(a - fn.start)
            if d <= best_d:
                best, best_d = i, d
        if best is not None:
            used.add(best)
            pairs.append((fn, gt[best]))
    return pairs


def e2e(root: Path, limit: int | None, engines: List[str]) -> None:
    runners: Dict[str, Callable] = {}
    if "basic-pitch" in engines:
        from pipeline import transcription
        runners["basic-pitch"] = lambda wav: map_notes_to_fretboard(transcription.transcribe(wav))
        runners["basic-pitch+dp"] = lambda wav: map_notes_to_fretboard_dp(transcription.transcribe(wav))
    if "synthtab" in engines:
        from pipeline import transcription_synthtab
        runners["synthtab"] = lambda wav: map_notes_to_fretboard(transcription_synthtab.transcribe(wav))
        runners["synthtab+dp"] = lambda wav: map_notes_to_fretboard_dp(transcription_synthtab.transcribe(wav))
        runners["synthtab-native"] = transcription_synthtab.transcribe_fretted
    stats = {k: [0, 0, 0, 0] for k in runners}  # matched, pred, gt, tab_ok
    files = tracks(root, limit)
    for n, jp in enumerate(files, 1):
        wav = root / "audio_mono-mic" / jp.name.replace(".jams", "_mic.wav")
        gt = load_jams(jp)
        for name, run in runners.items():
            pred = run(wav)
            pairs = _match(pred, gt)
            st = stats[name]
            st[0] += len(pairs)
            st[1] += len(pred)
            st[2] += len(gt)
            st[3] += sum(1 for fn, g in pairs if (fn.string, fn.fret) == (g[3], g[4]))
        print(f"  [{n}/{len(files)}] {jp.stem}", file=sys.stderr)

    print(f"{'engine':<16} {'precision':>9} {'recall':>7} {'F1':>6} {'tab acc':>8}  (tab acc = right string+fret among matched notes)")
    for name, (m, p, g, ok) in stats.items():
        prec, rec = m / max(p, 1), m / max(g, 1)
        f1 = 2 * prec * rec / max(prec + rec, 1e-9)
        print(f"{name:<16} {100*prec:8.1f}% {100*rec:6.1f}% {100*f1:5.1f}% {100*ok/max(m,1):7.1f}%")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("level", choices=["fingering", "e2e"])
    ap.add_argument("--root", type=Path, default=Path.home() / "datasets" / "GuitarSet")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--mapper", choices=["greedy", "dp"], default="dp")
    ap.add_argument("--players", default="", help="e.g. 03,04,05 to evaluate on held-out players")
    ap.add_argument("--engines", default="basic-pitch,synthtab")
    a = ap.parse_args()
    if a.level == "fingering":
        fingering(a.root, a.limit, a.mapper, a.players)
    else:
        e2e(a.root, a.limit, a.engines.split(","))
