@echo off
if not exist .venv (
  echo Run install.bat first.
  pause
  exit /b 1
)

call .venv\Scripts\activate.bat

echo.
echo   Notara running at http://localhost:8000
echo   Press Ctrl+C to stop.
echo.

start http://localhost:8000
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000
