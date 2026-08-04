@echo off
echo.
echo   Notara - Audio to Guitar Tab
echo.

if not exist .venv (
  echo ERROR: Not installed yet. Run install.bat first.
  pause
  exit /b 1
)

call .venv\Scripts\activate.bat
if %errorlevel% neq 0 (
  echo ERROR: Could not activate environment. Try running install.bat again.
  pause
  exit /b 1
)

echo   Starting server... please wait.
echo.

:: Start server in background, wait 5 seconds, then open browser
start /b python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --log-level warning

timeout /t 5 /nobreak >nul
start http://localhost:8000

echo   Notara is running at http://localhost:8000
echo   Keep this window open. Close it to stop Notara.
echo.

:: Keep window open and server running
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --log-level warning
