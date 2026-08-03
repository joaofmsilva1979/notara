"""Background worker — runs the full pipeline for a job."""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional

# Make repo root importable
sys.path.insert(0, str(Path(__file__).parent.parent))

import librosa

from pipeline import (
    chord_detection, fretboard, key_detection,
    separation, tab_render, transcription,
)
from pipeline import tuning as tuning_mod
from pipeline import vocal_tab as vocal_tab_mod
from pipeline import drum_summary as drum_summary_mod
from pipeline import piano_tab as piano_tab_mod
from pipeline.midi_export import export_midi
from pipeline.pdf_export import export_pdf
from pipeline.separation import DEMUCS_MODEL

from . import jobs as job_store


def _step(job: job_store.Job, n: int, label: str) -> None:
    job.step = n
    job.step_label = label
    job.status = "running"


def _count_steps(params: Dict[str, Any]) -> int:
    base = 4  # separate + transcribe g1 + key/chords + fretboard/render g1
    if params["multi_guitar"]:
        base += 1
    if params["bass_tab"]:
        base += 1
    if params["vocal_tab"]:
        base += 1
    if params["drum_summary"]:
        base += 1
    if params["keys_tab"]:
        base += 1
    return base


def run_job(job_id: str, params: Dict[str, Any]) -> None:
    job = job_store.get_job(job_id)
    if not job:
        return

    try:
        work_dir: Path = job.work_dir
        job.total_steps = _count_steps(params)
        step = 0

        # YouTube download
        if params.get("youtube_url"):
            step += 1
            _step(job, step, "Downloading from YouTube")
            audio_path = work_dir / "audio.mp3"
            subprocess.run(
                ["yt-dlp", "-x", "--audio-format", "mp3",
                 "-o", str(audio_path), params["youtube_url"]],
                check=True,
            )
            params["audio_path"] = audio_path
            job.total_steps += 1  # account for download step

        audio_path = Path(params["audio_path"])

        # Step: Separate
        step += 1
        _step(job, step, "Separating stems (Demucs)")
        if params["multi_guitar"]:
            guitar1_path, guitar2_path, bass_path, harmonic_path = \
                separation.separate_guitars(audio_path, work_dir)
        else:
            harmonic_path, bass_path = separation.separate(audio_path, work_dir)
            guitar1_path = harmonic_path
            guitar2_path = None

        # Step: Transcribe Guitar 1
        step += 1
        _step(job, step, "Transcribing Guitar 1")
        guitar_tuning_name = params["tuning"]
        if guitar_tuning_name in ("auto", "Standard EADGBE"):
            guitar_tuning = tuning_mod.find_tuning(tuning_mod.STANDARD_E_A_D_G_B_E)
        else:
            guitar_tuning = tuning_mod.find_tuning(guitar_tuning_name)
        notes1 = transcription.transcribe(guitar1_path)

        # Auto-detect tuning if "auto"
        if guitar_tuning_name == "auto":
            suggestion = tuning_mod.suggest_alternate_tuning(notes1, guitar_tuning)
            if suggestion:
                guitar_tuning = suggestion.suggested

        # Step: Key + Chords
        step += 1
        _step(job, step, "Detecting key & chords")
        y, sr = librosa.load(str(harmonic_path), sr=None, mono=True)
        bass_y, bass_sr = librosa.load(str(bass_path), sr=None, mono=True)
        key_est = key_detection.detect_key(y, sr)

        # Override key if user specified
        if params["key"] != "auto":
            parts = params["key"].split()
            if len(parts) == 2:
                key_est = key_detection.KeyEstimate(
                    tonic=parts[0], mode=parts[1], correlation=1.0
                )

        bars, tempo = chord_detection.detect_chords(y, sr, bass_y, bass_sr, key_est)

        # Step: Fretboard + render Guitar 1
        step += 1
        _step(job, step, "Mapping to fretboard + rendering tab")
        fretted1 = fretboard.map_notes_to_fretboard(notes1, guitar_tuning)
        # bars_per_line=1 for web display (bar-sync highlight requires one block per bar)
        tab1_web = tab_render.render_tab(
            bars, fretted1, key_est, tempo, audio_path.name, guitar_tuning, bars_per_line=1
        )
        tab1 = tab_render.render_tab(
            bars, fretted1, key_est, tempo, audio_path.name, guitar_tuning
        )
        (work_dir / "guitar1.txt").write_text(tab1, encoding="utf-8")
        export_pdf(
            work_dir / "guitar1.pdf", bars, fretted1, key_est, tempo,
            audio_path.name, guitar_tuning
        )
        export_midi(work_dir / "guitar1.midi", fretted1, tempo)

        results: Dict[str, Any] = {
            "tabs": {"guitar1": tab1_web},
            "key": str(key_est),
            "tempo": round(tempo, 1),
            "tuning": guitar_tuning.name,
            "bars": [
                {"label": b.label, "start_sec": round(b.start, 3),
                 "end_sec": round(b.end, 3)}
                for b in bars
            ],
        }

        # Optional: Guitar 2
        if params["multi_guitar"] and guitar2_path:
            step += 1
            _step(job, step, "Transcribing Guitar 2")
            notes2 = transcription.transcribe(guitar2_path)
            fretted2 = fretboard.map_notes_to_fretboard(notes2, guitar_tuning)
            tab2_web = tab_render.render_tab(
                bars, fretted2, key_est, tempo, audio_path.name, guitar_tuning, bars_per_line=1
            )
            tab2 = tab_render.render_tab(
                bars, fretted2, key_est, tempo, audio_path.name, guitar_tuning
            )
            (work_dir / "guitar2.txt").write_text(tab2, encoding="utf-8")
            export_pdf(
                work_dir / "guitar2.pdf", bars, fretted2, key_est, tempo,
                audio_path.name, guitar_tuning
            )
            export_midi(work_dir / "guitar2.midi", fretted2, tempo)
            results["tabs"]["guitar2"] = tab2_web

        # Optional: Bass tab
        if params["bass_tab"]:
            step += 1
            _step(job, step, "Transcribing bass")
            bass_tuning = tuning_mod.find_tuning(tuning_mod.BASS_STANDARD_EADG)
            bass_notes = transcription.transcribe(bass_path)
            bass_fretted = fretboard.map_notes_to_fretboard(bass_notes, bass_tuning)
            bass_tab_web = tab_render.render_tab(
                bars, bass_fretted, key_est, tempo, audio_path.name, bass_tuning, bars_per_line=1
            )
            bass_tab_text = tab_render.render_tab(
                bars, bass_fretted, key_est, tempo, audio_path.name, bass_tuning
            )
            (work_dir / "bass.txt").write_text(bass_tab_text, encoding="utf-8")
            export_pdf(
                work_dir / "bass.pdf", bars, bass_fretted, key_est, tempo,
                audio_path.name, bass_tuning
            )
            results["tabs"]["bass"] = bass_tab_web

        # Optional: Vocal melody
        if params["vocal_tab"]:
            step += 1
            _step(job, step, "Transcribing vocal melody")
            stem_dir = work_dir / "stems" / DEMUCS_MODEL / audio_path.stem
            vocal_path = stem_dir / "vocals.wav"
            if vocal_path.exists():
                vocal_text_web = vocal_tab_mod.render_vocal_tab(
                    vocal_path, bars, key_est, tempo, audio_path.name, bars_per_line=1
                )
                vocal_text = vocal_tab_mod.render_vocal_tab(
                    vocal_path, bars, key_est, tempo, audio_path.name
                )
                (work_dir / "vocals.txt").write_text(vocal_text, encoding="utf-8")
                results["tabs"]["vocals"] = vocal_text_web

        # Optional: Drum summary
        if params["drum_summary"]:
            step += 1
            _step(job, step, "Analysing drums")
            stem_dir = work_dir / "stems" / DEMUCS_MODEL / audio_path.stem
            drum_path = stem_dir / "drums.wav"
            if drum_path.exists():
                drum_text = drum_summary_mod.summarize_drums(drum_path, tempo)
                (work_dir / "drums.txt").write_text(drum_text, encoding="utf-8")
                results["tabs"]["drums"] = drum_text

        # Optional: Keys / Keyboard (Demucs piano stem)
        if params.get("keys_tab"):
            step += 1
            _step(job, step, "Transcribing keys/keyboard")
            stem_dir = work_dir / "stems" / DEMUCS_MODEL / audio_path.stem
            piano_path = stem_dir / "piano.wav"
            keys_result = piano_tab_mod.render_piano_tab(
                piano_path, bars=len(bars), key_est=str(key_est),
                tempo=tempo, source_name=audio_path.name
            )
            if keys_result:
                (work_dir / "keys.txt").write_text(keys_result["text"], encoding="utf-8")
                if keys_result["midi_bytes"]:
                    (work_dir / "keys.midi").write_bytes(keys_result["midi_bytes"])
                results["tabs"]["keys"] = keys_result["text"]

        job.results = results
        job.status = "done"
        job.step = job.total_steps
        job.step_label = "Done"

    except Exception as exc:
        job.status = "error"
        job.error = str(exc)
