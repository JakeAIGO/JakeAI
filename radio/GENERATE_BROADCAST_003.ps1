$ErrorActionPreference = "Stop"
$Repo = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Radio = Join-Path $Repo "radio"
$Ace = Join-Path $env:USERPROFILE "JakeAI\ACE-Step-1.5"
$Out = "C:\JakeAI\KJAI\Broadcast003\tracks"
$Log = "C:\JakeAI\KJAI\Broadcast003\Broadcast003_Generation_Log.txt"

New-Item -ItemType Directory -Force -Path $Out | Out-Null
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Log) | Out-Null

try { Stop-Transcript | Out-Null } catch {}
Start-Transcript -Path $Log -Force | Out-Null

function Banner($t) {
  Write-Host ""
  Write-Host "============================================================"
  Write-Host $t
  Write-Host "============================================================"
}

try {
  Banner "KJAI BROADCAST 003 — PRIVATE MUSIC GENERATION"
  Write-Host "Public release: NO"
  Write-Host "Founder voice used in songs: NO"
  Write-Host "Six new original tracks will be rendered locally with ACE-Step."
  Write-Host ""

  if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw "Git is required."
  }

  $uvExe = (Get-Command uv -ErrorAction SilentlyContinue).Source
  if (-not $uvExe) {
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) { throw "uv is missing and winget is unavailable." }
    & winget install --id=astral-sh.uv -e --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) { throw "uv installation failed." }
    $uvExe = (Get-Command uv -ErrorAction SilentlyContinue).Source
    if (-not $uvExe) { $uvExe = Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Links\uv.exe" }
  }

  if (-not (Test-Path (Join-Path $Ace "pyproject.toml"))) {
    Banner "DOWNLOADING ACE-STEP 1.5"
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Ace) | Out-Null
    & git clone https://github.com/ACE-Step/ACE-Step-1.5.git $Ace
    if ($LASTEXITCODE -ne 0) { throw "ACE-Step clone failed." }
  }

  Banner "VERIFYING ACE-STEP"
  Set-Location $Ace
  & $uvExe sync
  if ($LASTEXITCODE -ne 0) { throw "ACE-Step dependency sync failed." }

  $health = $false
  try {
    $r = Invoke-RestMethod -Uri "http://127.0.0.1:8001/health" -TimeoutSec 3
    if ($r.code -eq 200) { $health = $true }
  } catch {}

  if (-not $health) {
    Banner "STARTING LOCAL MUSIC ENGINE"
    Start-Process -FilePath "cmd.exe" -ArgumentList "/k", "cd /d `"$Ace`" && set ACESTEP_INIT_LLM=false && `"$uvExe`" run acestep-api --host 127.0.0.1 --port 8001"
    Write-Host "Waiting for ACE-Step..."
    for ($i=0; $i -lt 180; $i++) {
      Start-Sleep -Seconds 5
      try {
        $r = Invoke-RestMethod -Uri "http://127.0.0.1:8001/health" -TimeoutSec 3
        if ($r.code -eq 200) { $health = $true; break }
      } catch {}
    }
  }
  if (-not $health) { throw "ACE-Step did not become healthy." }

  Banner "RENDERING BROADCAST 003 MUSIC"
  Set-Location $Repo
  py -3.11 radio\music_factory_kjai404.py --prompts radio\artist_song_specs_v2.json --out "$Out"
  if ($LASTEXITCODE -ne 0) { throw "Broadcast 003 music generation failed." }

  Banner "BROADCAST 003 MUSIC COMPLETE"
  Write-Host "Six tracks are ready for private audition."
  Write-Host "Nothing has been published."
  Start-Process explorer.exe $Out
} catch {
  Banner "FAILED"
  Write-Host $_.Exception.Message
  Write-Host "Log: $Log"
  try { Stop-Transcript | Out-Null } catch {}
  Start-Process notepad.exe $Log
  Read-Host "Press Enter to close"
  exit 1
}

try { Stop-Transcript | Out-Null } catch {}
Read-Host "Press Enter to close"
