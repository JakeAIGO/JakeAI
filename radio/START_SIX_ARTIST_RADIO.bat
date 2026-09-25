@echo off
setlocal
cd /d "%~dp0"
title JakeAI Radio Six Artist Batch
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0GENERATE_SIX_ARTISTS.ps1"
