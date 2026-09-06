@echo off
echo.
echo   Notara - Audio to Guitar Tab
echo   Installing dependencies...
echo.

:: Check Python is available
python --version >nul 2>&1
if %errorlevel% neq 0 (
  echo ERROR: Python not found.
  echo.
  echo   1. Go to https://www.python.org/downloads/release/python-3119/
  echo   2. Download "Windows installer (64-bit)" for Python 3.11
  echo   3. IMPORTANT: tick "Add Python to PATH" during install
  echo   4. Close this window and run install.bat again
  echo.
  pause
  exit /b 1
)

echo   Python found:
python --version
echo.

:: Warn if Python version is too new (3.12+ has issues with some ML packages)
for /f "tokens=2 delims=." %%a in ('python --version 2^>^&1') do set PYMINOR=%%a
if %PYMINOR% GEQ 12 (
  echo WARNING: Python 3.%PYMINOR% detected. Some packages work best with Python 3.11.
  echo If installation fails, reinstall Python 3.11 from:
  echo   https://www.python.org/downloads/release/python-3119/
  echo.
)

:: Create virtual environment
echo   Creating virtual environment...
python -m venv .venv
if %errorlevel% neq 0 (
  echo ERROR: Could not create virtual environment.
  pause
  exit /b 1
)

:: Activate and install
call .venv\Scripts\activate.bat
echo   Installing packages (this takes a few minutes on first run)...
python -m pip install --upgrade pip -q
pip install -r api\requirements.txt
if %errorlevel% neq 0 (
  echo.
  echo ERROR: Package installation failed. Check the error above.
  pause
  exit /b 1
)

:: Check ffmpeg (required by yt-dlp for YouTube downloads)
ffmpeg -version >nul 2>&1
if %errorlevel% neq 0 (
  echo.
  echo   WARNING: ffmpeg not found - YouTube downloads will not work.
  echo   To fix this:
  echo     1. Go to https://www.gyan.dev/ffmpeg/builds/
  echo     2. Download "ffmpeg-release-essentials.zip"
  echo     3. Extract it and copy ffmpeg.exe to this folder
  echo        (same folder as install.bat)
  echo.
) else (
  echo   ffmpeg found - YouTube downloads enabled.
)

echo.
echo   ────────────────────────────────────────
echo   Installation complete!
echo   Run start.bat to launch Notara.
echo   ────────────────────────────────────────
echo.
pause
