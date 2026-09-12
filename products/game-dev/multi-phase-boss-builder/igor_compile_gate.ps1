param(
    [Parameter(Mandatory=$true)][string]$Project,
    [Parameter(Mandatory=$true)][string]$RuntimePath,
    [Parameter(Mandatory=$true)][string]$UserFolder,
    [string]$Platform = 'Windows',
    [string]$IgorPath = ''
)

$ErrorActionPreference = 'Stop'

if (-not (Test-Path $Project)) { throw "Project not found: $Project" }
if (-not (Test-Path $RuntimePath)) { throw "Runtime path not found: $RuntimePath" }
if (-not (Test-Path $UserFolder)) { throw "GameMaker user folder not found: $UserFolder" }

if ([string]::IsNullOrWhiteSpace($IgorPath)) {
    $candidates = Get-ChildItem -Path $RuntimePath -Recurse -Filter 'Igor.exe' -ErrorAction SilentlyContinue
    if ($candidates.Count -eq 0) { throw 'Igor.exe not found under supplied runtime path.' }
    $IgorPath = $candidates[0].FullName
}

$root = Split-Path -Parent $Project
$cache = Join-Path $root '.igor-cache'
$temp = Join-Path $root '.igor-temp'
New-Item -ItemType Directory -Force -Path $cache, $temp | Out-Null

Write-Host 'JakeAI GameMaker compile gate'
Write-Host "Project: $Project"
Write-Host "Igor: $IgorPath"
Write-Host "Platform: $Platform"

& $IgorPath "/uf=$UserFolder" "/rp=$RuntimePath" "/project=$Project" "/cache=$cache" "/temp=$temp" -- $Platform Compile
$code = $LASTEXITCODE
if ($code -ne 0) { throw "GameMaker compile failed with exit code $code" }

Write-Host 'PASS: GameMaker Igor compile completed successfully.'
