@echo off
setlocal
cd /d "%~dp0"
echo.
echo JAKEAI EDITIONS - FOUNDER VOICE BATCH
echo =====================================
echo Private local render only. Nothing will be uploaded or published.
echo.

if not exist ".venv\Scripts\python.exe" (
  echo Local narration environment is missing.
  echo Run setup_founder_narrator_windows.bat first.
  pause
  exit /b 1
)

set "EPUBDIR=C:\JakeAI\Editions\ReadyEPUBs"
set "OUTDIR=C:\JakeAI\Editions\FounderNarration"

if "%JAKEAI_FOUNDER_VOICE%"=="" (
  set /p "VOICE=Paste the full path to your private founder voice WAV: "
) else (
  set "VOICE=%JAKEAI_FOUNDER_VOICE%"
)

if not exist "%VOICE%" (
  echo.
  echo Founder voice file not found:
  echo %VOICE%
  pause
  exit /b 1
)
if not exist "%EPUBDIR%" mkdir "%EPUBDIR%"
if not exist "%OUTDIR%" mkdir "%OUTDIR%"

echo.
echo EPUB input: %EPUBDIR%
echo Output:     %OUTDIR%
echo Voice:      PRIVATE LOCAL REFERENCE
echo.
echo The renderer will process every JAE-*.epub in the input folder,
echo resume partial books, and skip finished books.
echo.
call ".venv\Scripts\activate.bat"
python render_founder_batch.py --epub-dir "%EPUBDIR%" --voice "%VOICE%" --out-dir "%OUTDIR%" --device auto
echo.
pause
