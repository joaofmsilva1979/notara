#!/bin/bash
set -e

if [ ! -d ".venv" ]; then
  echo "Run ./install.sh first."
  exit 1
fi

source .venv/bin/activate

echo ""
echo "  Notara running at http://localhost:8000"
echo "  Press Ctrl+C to stop."
echo ""

# Open browser on macOS
if [[ "$(uname)" == "Darwin" ]]; then
  sleep 1 && open http://localhost:8000 &
fi

python3 -m uvicorn api.main:app --host 0.0.0.0 --port 8000
