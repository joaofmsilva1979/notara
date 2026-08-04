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
  echo   1. Go to https://python.org/downloads
  echo   2. Download and run the installer
  echo   3. IMPORTANT: tick "Add Python to PATH" during install
  echo   4. Close this window and run install.bat again
  echo.
  pause
  exit /b 1
)

echo   Python found:
python --version
echo.

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

echo.
echo   ────────────────────────────────────────
echo   Installation complete!
echo   Run start.bat to launch Notara.
echo   ────────────────────────────────────────
echo.
pause
