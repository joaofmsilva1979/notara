#!/bin/bash
set -e

echo ""
echo "  Notara — Audio to Guitar Tab"
echo "  Installing dependencies..."
echo ""

# Check Python 3.9+
if ! command -v python3 &>/dev/null; then
  echo "ERROR: Python 3 not found. Install it from https://python.org and try again."
  exit 1
fi

PY_VER=$(python3 -c "import sys; print(sys.version_info.minor)")
if [ "$PY_VER" -lt 9 ]; then
  echo "ERROR: Python 3.9 or newer is required (you have 3.$PY_VER)."
  exit 1
fi

# Create virtual environment
echo "Creating virtual environment..."
python3 -m venv .venv

# Activate
source .venv/bin/activate

# Upgrade pip silently
pip install --upgrade pip -q

# Install dependencies
echo "Installing Python packages (this may take a few minutes)..."
pip install -r api/requirements.txt -q

# macOS: add CoreML acceleration for basic-pitch
if [[ "$(uname)" == "Darwin" ]]; then
  echo "macOS detected — adding CoreML acceleration..."
  pip install "basic-pitch[coreml]>=0.4.0" -q
fi

# Check ffmpeg (required by yt-dlp for YouTube downloads)
if ! command -v ffmpeg &>/dev/null; then
  echo ""
  echo "  WARNING: ffmpeg not found — YouTube downloads will not work."
  if [[ "$(uname)" == "Darwin" ]]; then
    echo "  Install it with Homebrew:"
    echo "    brew install ffmpeg"
  else
    echo "  Install it with:"
    echo "    sudo apt install ffmpeg   (Ubuntu/Debian)"
    echo "    sudo dnf install ffmpeg   (Fedora)"
  fi
  echo ""
else
  echo "ffmpeg found: $(ffmpeg -version 2>&1 | head -1)"
fi

echo ""
echo "  Done! To start Notara, run:"
echo ""
echo "    ./start.sh"
echo ""
