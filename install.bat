@echo off
echo.
echo   Notara - Audio to Guitar Tab
echo   Installing dependencies...
echo.

python --version >nul 2>&1
if %errorlevel% neq 0 (
  echo ERROR: Python not found. Install it from https://python.org and try again.
  pause
  exit /b 1
)

echo Creating virtual environment...
python -m venv .venv

echo Installing Python packages (this may take a few minutes)...
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip -q
pip install -r api\requirements.txt -q

echo.
echo   Done! To start Notara, run:
echo.
echo     start.bat
echo.
pause
