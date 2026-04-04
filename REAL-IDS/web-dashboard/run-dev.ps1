# REAL-IDS Observatory - dev start (local npm cache to avoid EPERM on D:\ node_cache)
# Usage: cd web-dashboard
#   powershell -ExecutionPolicy Bypass -File .\run-dev.ps1
# Or from current folder: .\run-dev.ps1

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$cacheDir = Join-Path $PSScriptRoot ".npm-cache"
New-Item -ItemType Directory -Force -Path $cacheDir | Out-Null
$env:npm_config_cache = $cacheDir

if (-not (Test-Path ".env")) {
  Copy-Item ".env.example" ".env"
  Write-Host 'Created .env from .env.example - edit VITE_REAL_IDS_URL if needed.' -ForegroundColor Yellow
}

Write-Host ('npm cache: ' + $cacheDir) -ForegroundColor Cyan
npm install
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

npx vite --host 127.0.0.1
