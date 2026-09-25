@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  echo Python 3.11 is required. Install Python 3.11, then run this again.
  pause
  exit /b 1
)
if not exist .venv (
  py -3.11 -m venv .venv
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install chatterbox-tts
echo.
echo JakeAI Local Narrator is ready.
echo Model weights will download once on the first narration run, then can be reused locally.
pause
