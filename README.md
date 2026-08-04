# Notara

Turn any audio file or YouTube link into guitar tabs, bass lines, vocal melody, drum patterns, and chord charts — free, no account needed, runs on your computer.

## What it does

- Guitar tab (single or multi-track stereo split)
- Bass tab
- Vocal melody (guitar octave notation)
- Drum summary (groove map + pattern)
- Keys / Keyboard (MIDI export)
- Lyrics + chord chart (upload your lyrics, get chords aligned above the words)

Export to PDF, TXT, or MIDI.

## Requirements

- Python 3.9 or newer — [python.org](https://python.org)
- macOS, Linux, or Windows
- ~4 GB free disk space (for ML models downloaded on first run)
- ~2 GB RAM minimum

## Install

**macOS / Linux**
```bash
git clone https://github.com/joaofmsilva1979/notara.git
cd notara
chmod +x install.sh start.sh
./install.sh
```

**Windows**
```
git clone https://github.com/joaofmsilva1979/notara.git
cd notara
install.bat
```

Installation downloads all Python dependencies including Demucs (source separation) and Whisper (lyrics alignment). This takes a few minutes on first run.

## Run

**macOS / Linux**
```bash
./start.sh
```

**Windows**
```
start.bat
```

Then open [http://localhost:8000](http://localhost:8000) in your browser. On macOS it opens automatically.

On first job, the ML models are downloaded (~1.5 GB). Subsequent runs are faster.

## How to use

1. Drop an audio file (MP3, WAV, M4A, FLAC, OGG — up to 100 MB) or paste a YouTube URL
2. Optionally upload a lyrics file (.txt or .docx) or paste lyrics to get a chord chart
3. Pick tuning, key, and which tracks you want
4. Hit TRANSCRIBE
5. Download tabs as PDF, TXT, or MIDI

## Notes

- Processing takes 1–5 minutes depending on song length and your hardware
- Chord detection and tab accuracy depend on the mix quality — clean recordings work best
- The tool runs entirely on your machine — no audio is sent to any server

## Support

If Notara saved you time, consider buying a coffee: [ko-fi.com/notaratabs](https://ko-fi.com/notaratabs)

## License

MIT
