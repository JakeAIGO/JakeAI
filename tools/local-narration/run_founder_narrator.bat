@echo off
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo Run setup_founder_narrator_windows.bat first.
  pause
  exit /b 1
)
echo.
echo JAKEAI FOUNDER NARRATOR V1
echo =========================
set /p EPUB=Path to verified JakeAI EPUB: 
set /p VOICE=Path to private founder reference WAV: 
set /p OUT=Output folder: 
".venv\Scripts\python.exe" founder_narrator_v1.py --epub "%EPUB%" --voice "%VOICE%" --out "%OUT%" --device auto
echo.
pause
