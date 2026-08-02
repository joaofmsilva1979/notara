#!/usr/bin/env python3
"""Audio -> approximate guitar tab pipeline.

Pipeline: Demucs separation -> basic-pitch polyphonic transcription ->
key detection (chroma + Krumhansl-Schmuckler) -> chord detection
(chroma template matching, bass-root and diatonic-key aware, hysteresis-
smoothed) -> tuning-aware fretboard mapping (see --tuning) -> ASCII tab
export.

See pipeline/*.py module docstrings for the known limitations of each stage
(chord ambiguity, non-idiomatic fret positions, dependency on Demucs
separation quality, 4/4-only rhythm quantization, etc). This is a best-effort
approximation, not a substitute for a human transcriber.

Usage:
    python main.py path/to/song.wav [--output out.txt] [--device cpu]
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import librosa

from pipeline import chord_detection, fretboard, key_detection, midi_export, pdf_export, separation, tab_render, transcription, tuning, voice_split


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("audio_path", type=Path, help="Input .wav file")
    parser.add_argument("--output", type=Path, default=None,
                         help="Output .txt path (default: <input>_tab.txt next to input)")
    parser.add_argument("--device", default="cpu", choices=["cpu", "cuda", "mps"],
                         help="Device for Demucs separation (default: cpu)")
    parser.add_argument("--keep-stems", action="store_true", default=True,
                         help="Keep Demucs stems on disk next to the output (default: on)")
    parser.add_argument("--export-midi", action="store_true",
                         help="Also export the quantized/fretted notes as a .mid file")
    parser.add_argument("--export-pdf", action="store_true",
                         help="Also export a printable PDF (Courier, portrait, "
                              "paginated) of the main tab")
    parser.add_argument("--pdf-font-size", type=int, default=8, choices=[7, 8],
                         help="Font size for --export-pdf output (default: %(default)s)")
    parser.add_argument("--voices", type=int, default=1, choices=[1, 2],
                         help="1 = single combined tab (default). "
                              "2 = also split into a treble-register and a "
                              "bass-register tab (heuristic, see voice_split.py "
                              "docstring -- NOT true two-guitar separation)")
    parser.add_argument("--tuning", default=tuning.STANDARD_E_A_D_G_B_E,
                         choices=[t.name for t in tuning.TUNINGS],
                         help="Guitar tuning to assume before fretboard mapping "
                              "(default: %(default)s)")
    parser.add_argument("--multi-guitar", action="store_true", default=False,
                         help="Separate into guitar 1 (left), guitar 2 (right), and bass — "
                              "produces three tab files instead of one. Works best for "
                              "stereo recordings with guitars panned left/right.")
    parser.add_argument("--bass-tuning", default=tuning.BASS_STANDARD_EADG,
                         choices=[t.name for t in tuning.BASS_TUNINGS],
                         help="Bass guitar tuning for --multi-guitar output "
                              f"(default: {tuning.BASS_STANDARD_EADG})")
    return parser.parse_args(argv)


def main() -> None:
    args = parse_args()
    audio_path: Path = args.audio_path.expanduser().resolve()
    if not audio_path.exists():
        print(f"Input file not found: {audio_path}", file=sys.stderr)
        sys.exit(1)

    output_path = args.output or audio_path.with_name(f"{audio_path.stem}_tab.txt")
    work_dir = audio_path.parent / f".{audio_path.stem}_pipeline_tmp"
    work_dir.mkdir(exist_ok=True)

    try:
        if args.multi_guitar:
            print("[1/8] Separating sources with Demucs (htdemucs_6s, multi-guitar mode)...")
            guitar1_path, guitar2_path, bass_stem_path, harmonic_path = separation.separate_guitars(
                audio_path, work_dir, device=args.device
            )

            print("[2/8] Transcribing Guitar 1 (left channel)...")
            notes_g1 = transcription.transcribe(guitar1_path)
            print(f"       -> {len(notes_g1)} notes detected")

            if guitar2_path is not None:
                print("[3/8] Transcribing Guitar 2 (right channel)...")
                notes_g2 = transcription.transcribe(guitar2_path)
                print(f"       -> {len(notes_g2)} notes detected")
            else:
                print("[3/8] Mono source — single guitar track only (no Guitar 2)")
                notes_g2 = None

            print("[4/8] Transcribing bass...")
            notes_bass = transcription.transcribe(bass_stem_path)
            print(f"       -> {len(notes_bass)} notes detected")

            print("[5/8] Confirming tuning...")
            selected_tuning = tuning.find_tuning(args.tuning)
            suggestion = tuning.suggest_alternate_tuning(notes_g1, selected_tuning)
            if suggestion is not None:
                print(f"       NOTE: {selected_tuning.name} doesn't fully match Guitar 1.")
                print(f"       Suggestion: {suggestion.suggested.name} "
                      f"(confidence={suggestion.confidence:.2f}). Re-run with "
                      f"--tuning \"{suggestion.suggested.name}\" if that's correct.")
            else:
                print(f"       -> {selected_tuning.name} confirmed")

            print("[6/8] Detecting key and chords...")
            y, sr = librosa.load(harmonic_path, sr=None, mono=True)
            bass_y, bass_sr = librosa.load(bass_stem_path, sr=None, mono=True)
            key_estimate = key_detection.detect_key(y, sr)
            print(f"       -> Key: {key_estimate} (correlation={key_estimate.correlation:.2f})")
            chords, tempo = chord_detection.detect_chords(y, sr, bass_y, bass_sr, key_estimate)
            print(f"       -> {len(chords)} bars, tempo ~{tempo:.1f} BPM")

            print("[7/8] Mapping notes to fretboard...")
            fretted_g1 = fretboard.map_notes_to_fretboard(notes_g1, selected_tuning)
            fretted_g2 = fretboard.map_notes_to_fretboard(notes_g2, selected_tuning) if notes_g2 else []
            bass_tuning_obj = tuning.find_tuning(args.bass_tuning)
            fretted_bass = fretboard.map_notes_to_fretboard(notes_bass, bass_tuning_obj)

            print("[8/8] Rendering tabs...")
            g1_label = f"{audio_path.name} (guitare 1 — canal gauche)"
            g1_path = output_path.with_name(f"{output_path.stem}_guitare1.txt")
            tab_render.write_tab(g1_path, chords, fretted_g1, key_estimate, tempo,
                                  g1_label, tuning=selected_tuning)

            if notes_g2 is not None:
                g2_label = f"{audio_path.name} (guitare 2 — canal droit)"
                g2_path = output_path.with_name(f"{output_path.stem}_guitare2.txt")
                tab_render.write_tab(g2_path, chords, fretted_g2, key_estimate, tempo,
                                      g2_label, tuning=selected_tuning)

            bass_label = f"{audio_path.name} (basse — {bass_tuning_obj.name})"
            bass_tab_path = output_path.with_name(f"{output_path.stem}_basse.txt")
            tab_render.write_tab(bass_tab_path, chords, fretted_bass, key_estimate, tempo,
                                  bass_label, tuning=bass_tuning_obj)

            if args.export_pdf:
                pdf_export.export_pdf(
                    g1_path.with_suffix(".pdf"), chords, fretted_g1, key_estimate, tempo,
                    g1_label, selected_tuning, font_size=args.pdf_font_size
                )
                if notes_g2 is not None:
                    pdf_export.export_pdf(
                        g2_path.with_suffix(".pdf"), chords, fretted_g2, key_estimate, tempo,
                        g2_label, selected_tuning, font_size=args.pdf_font_size
                    )
                pdf_export.export_pdf(
                    bass_tab_path.with_suffix(".pdf"), chords, fretted_bass, key_estimate, tempo,
                    bass_label, bass_tuning_obj, font_size=args.pdf_font_size
                )

            outputs = [str(g1_path)]
            if notes_g2 is not None:
                outputs.append(str(g2_path))
            outputs.append(str(bass_tab_path))
            print(f"\nDone. Tabs written to: {', '.join(outputs)}")

        else:
            print("[1/7] Separating sources with Demucs (htdemucs_6s)...")
            harmonic_path, bass_stem_path = separation.separate(audio_path, work_dir, device=args.device)

            print("[2/7] Transcribing notes with basic-pitch...")
            notes = transcription.transcribe(harmonic_path)
            print(f"       -> {len(notes)} notes detected")

            print("[3/7] Confirming tuning...")
            selected_tuning = tuning.find_tuning(args.tuning)
            suggestion = tuning.suggest_alternate_tuning(notes, selected_tuning)
            if suggestion is not None:
                print(f"       NOTE: {selected_tuning.name} doesn't fully match what's heard.")
                print(f"       Suggestion: {suggestion.suggested.name} "
                      f"(confidence={suggestion.confidence:.2f}). Re-run with "
                      f"--tuning \"{suggestion.suggested.name}\" if that's correct.")
            else:
                print(f"       -> {selected_tuning.name} confirmed")

            print("[4/7] Loading harmonic mix for key/chord analysis...")
            y, sr = librosa.load(harmonic_path, sr=None, mono=True)
            bass_y, bass_sr = librosa.load(bass_stem_path, sr=None, mono=True)

            print("[5/7] Detecting key (chroma + Krumhansl-Schmuckler)...")
            key_estimate = key_detection.detect_key(y, sr)
            print(f"       -> {key_estimate} (correlation={key_estimate.correlation:.2f})")

            print("[6/7] Detecting chords (bass-root + diatonic-key aware, hysteresis-smoothed)...")
            chords, tempo = chord_detection.detect_chords(y, sr, bass_y, bass_sr, key_estimate)
            print(f"       -> {len(chords)} bars, tempo ~{tempo:.1f} BPM")

            print("[7/7] Mapping notes to fretboard and rendering tab...")
            fretted_notes = fretboard.map_notes_to_fretboard(notes, selected_tuning)
            tab_render.write_tab(output_path, chords, fretted_notes, key_estimate, tempo,
                                  audio_path.name, tuning=selected_tuning)

            if args.voices == 2:
                treble_notes, bass_notes = voice_split.split_voices(fretted_notes)
                treble_path = output_path.with_name(f"{output_path.stem}_guitare_aigue.txt")
                bass_path = output_path.with_name(f"{output_path.stem}_guitare_grave.txt")
                treble_strings = "/".join(selected_tuning.string_names[3:])
                bass_strings = "/".join(selected_tuning.string_names[:3])
                treble_label = f"{audio_path.name} (voix aigue {treble_strings} -- heuristique, pas une vraie 2e guitare)"
                bass_label = f"{audio_path.name} (voix grave {bass_strings} -- heuristique, pas une vraie 2e guitare)"
                tab_render.write_tab(treble_path, chords, treble_notes, key_estimate, tempo,
                                      treble_label, tuning=selected_tuning)
                tab_render.write_tab(bass_path, chords, bass_notes, key_estimate, tempo,
                                      bass_label, tuning=selected_tuning)
                print(f"Voice split: {treble_path}, {bass_path}")

                if args.export_pdf:
                    treble_pdf_path = output_path.with_name(f"{output_path.stem}_guitare_aigue.pdf")
                    bass_pdf_path = output_path.with_name(f"{output_path.stem}_guitare_grave.pdf")
                    pdf_export.export_pdf(treble_pdf_path, chords, treble_notes, key_estimate, tempo,
                                           treble_label, selected_tuning, font_size=args.pdf_font_size)
                    pdf_export.export_pdf(bass_pdf_path, chords, bass_notes, key_estimate, tempo,
                                           bass_label, selected_tuning, font_size=args.pdf_font_size)
                    print(f"Voice split PDF: {treble_pdf_path}, {bass_pdf_path}")

            if args.export_midi:
                midi_path = output_path.with_suffix(".mid")
                midi_export.export_midi(midi_path, fretted_notes, tempo)
                print(f"MIDI export: {midi_path}")

            if args.export_pdf:
                pdf_path = output_path.with_suffix(".pdf")
                pdf_export.export_pdf(pdf_path, chords, fretted_notes, key_estimate, tempo,
                                       audio_path.name, selected_tuning, font_size=args.pdf_font_size)
                print(f"PDF export: {pdf_path}")

            print(f"\nDone. Tab written to: {output_path}")

    finally:
        if args.keep_stems:
            stems_dest = output_path.parent / f"{audio_path.stem}_stems"
            src_stems = work_dir / "stems"
            if src_stems.exists():
                if stems_dest.exists():
                    shutil.rmtree(stems_dest)
                shutil.move(str(src_stems), str(stems_dest))
        shutil.rmtree(work_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
