@echo off
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo Run setup_windows.bat first.
  pause
  exit /b 1
)
echo.
echo JAKEAI ORIGINAL AI NARRATION - LOCAL RUNNER
echo No per-character API billing. The reference voice stays on this computer.
echo.
set /p EPUB=Path to JakeAI EPUB release candidate: 
set /p VOICE=Path to private founder reference WAV: 
set /p OUT=Output folder: 
".venv\Scripts\python.exe" narrate_epub.py --epub "%EPUB%" --voice "%VOICE%" --out "%OUT%" --device auto
echo.
pause
