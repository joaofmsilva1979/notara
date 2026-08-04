#!/bin/bash
# Notara — double-click to install and launch
# -----------------------------------------------

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
BOLD='\033[1m'
NC='\033[0m'

clear
echo ""
echo -e "${BOLD}  ♩ NOTARA — Audio to Guitar Tab${NC}"
echo "  ─────────────────────────────────"
echo ""

# Move to the folder where this script lives
cd "$(dirname "$0")"

# ── Step 1: Check Python ────────────────────────────────
echo "  Checking Python..."

install_python() {
  echo ""
  echo -e "  ${RED}Python 3.9+ is required but not found.${NC}"
  echo ""
  echo "  Installing Homebrew + Python automatically..."
  echo "  (You may be asked for your Mac password)"
  echo ""

  # Install Homebrew if missing
  if ! command -v brew &>/dev/null; then
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    # Add brew to PATH for Apple Silicon
    eval "$(/opt/homebrew/bin/brew shellenv)" 2>/dev/null || true
    eval "$(/usr/local/bin/brew shellenv)" 2>/dev/null || true
  fi

  brew install python@3.11
  echo ""
  echo -e "  ${GREEN}Python installed!${NC}"
}

PYTHON=""
for cmd in python3.11 python3.10 python3.9 python3; do
  if command -v "$cmd" &>/dev/null; then
    VER=$("$cmd" -c "import sys; print(sys.version_info.minor)")
    MAJOR=$("$cmd" -c "import sys; print(sys.version_info.major)")
    if [ "$MAJOR" -eq 3 ] && [ "$VER" -ge 9 ]; then
      PYTHON="$cmd"
      break
    fi
  fi
done

if [ -z "$PYTHON" ]; then
  install_python
  PYTHON="python3"
fi

echo -e "  ${GREEN}Python OK ($($PYTHON --version))${NC}"
echo ""

# ── Step 2: Create venv if not already done ─────────────
if [ ! -d ".venv" ]; then
  echo "  Installing Notara (first time — takes a few minutes)..."
  echo ""
  $PYTHON -m venv .venv
  source .venv/bin/activate
  pip install --upgrade pip -q
  pip install -r api/requirements.txt -q
  pip install "basic-pitch[coreml]>=0.4.0" -q
  echo ""
  echo -e "  ${GREEN}Installation complete!${NC}"
else
  echo "  Notara already installed."
  source .venv/bin/activate
fi

echo ""

# ── Step 3: Launch ──────────────────────────────────────
echo -e "  ${BOLD}Starting Notara...${NC}"
echo "  Opening http://localhost:8000 in your browser."
echo ""
echo "  To stop: close this window or press Ctrl+C"
echo "  ─────────────────────────────────"
echo ""

sleep 1 && open http://localhost:8000 &
python3 -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --log-level warning
