$ErrorActionPreference = "Stop"
$Repo = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Radio = Join-Path $Repo "radio"
$Ace = Join-Path $env:USERPROFILE "JakeAI\ACE-Step-1.5"
$Out = Join-Path $Radio "private-generated-six-artist-v1"
$Log = Join-Path $Radio "SIX_ARTIST_BATCH_LOG.txt"

try { Stop-Transcript | Out-Null } catch {}
Start-Transcript -Path $Log -Force | Out-Null

function Banner($t) {
  Write-Host ""
  Write-Host "============================================================"
  Write-Host $t
  Write-Host "============================================================"
}

try {
  Banner "JAKEAI RADIO — SIX ARTIST PRIVATE BATCH"
  Write-Host "Founder/DJ voice used in songs: NO"
  Write-Host "Creative Claw: NOT USED"
  Write-Host "Paid music API: NOT USED"
  Write-Host "Public release: NO"
  Write-Host ""

  if (-not (Test-Path $Ace)) {
    throw "ACE-Step is not installed at $Ace. Run the earlier JakeAI Radio local sampler setup first."
  }

  $uv = Get-Command uv -ErrorAction SilentlyContinue
  if (-not $uv) {
    $candidate = Join-Path $env:USERPROFILE ".local\bin\uv.exe"
    if (Test-Path $candidate) { $env:Path = (Split-Path $candidate) + ";" + $env:Path }
  }
  if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw "uv is not available. Run the JakeAI Radio sampler setup once first."
  }

  New-Item -ItemType Directory -Force -Path $Out | Out-Null

  Banner "STARTING LOCAL ACE-STEP"
  $health = $false
  try {
    $r = Invoke-RestMethod -Uri "http://127.0.0.1:8001/health" -TimeoutSec 3
    if ($r.code -eq 200) { $health = $true }
  } catch {}

  if (-not $health) {
    Start-Process -FilePath "cmd.exe" -ArgumentList "/k", "cd /d `"$Ace`" && set ACESTEP_INIT_LLM=false && uv run acestep-api --host 127.0.0.1 --port 8001"
    Write-Host "Waiting for the local music engine..."
    for ($i=0; $i -lt 180; $i++) {
      Start-Sleep -Seconds 5
      try {
        $r = Invoke-RestMethod -Uri "http://127.0.0.1:8001/health" -TimeoutSec 3
        if ($r.code -eq 200) { $health = $true; break }
      } catch {}
    }
  }
  if (-not $health) { throw "ACE-Step did not become healthy." }

  Banner "RENDERING SIX FICTIONAL ARTISTS"
  Set-Location $Repo
  py -3.11 radio\music_factory_kjai404.py --out "$Out"
  if ($LASTEXITCODE -ne 0) { throw "Six-artist generation failed." }

  Banner "PRIVATE BATCH COMPLETE"
  Write-Host "Open the output folder and audition the tracks."
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
