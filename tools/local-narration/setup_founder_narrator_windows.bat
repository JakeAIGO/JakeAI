@echo off
setlocal
cd /d "%~dp0"
echo.
echo JAKEAI FOUNDER NARRATOR V1 - WINDOWS SETUP
echo ==========================================
echo.
where py >nul 2>nul
if errorlevel 1 (
  echo Python 3.11 is required.
  pause
  exit /b 1
)
if not exist .venv (
  py -3.11 -m venv .venv
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip setuptools wheel
pip install "numpy>=1.24,<2.0"
pip install --index-url https://download.pytorch.org/whl/cpu "torch==2.6.0" "torchaudio==2.6.0"
pip install --upgrade resemble-perth
pip install "librosa==0.11.0" s3tokenizer "transformers==5.2.0" "diffusers==0.29.0" "conformer==0.3.2" "safetensors==0.5.3" pyloudnorm omegaconf huggingface_hub
pip install --no-deps "chatterbox-tts==0.1.7"
echo.
echo Setup complete.
echo Production mode requires a working PerthImplicitWatermarker.
pause
