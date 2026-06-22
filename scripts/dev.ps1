# Local development launcher (Windows / PowerShell, no Docker required).
# Usage:  powershell -ExecutionPolicy Bypass -File scripts\dev.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env from .env.example — edit it to set OPENROUTER_API_KEY/OPERATOR_TOKEN." -ForegroundColor Yellow
}

$venvPy = "backend\.venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) {
    Write-Host "Creating backend virtualenv..." -ForegroundColor Cyan
    py -3.11 -m venv backend\.venv
    & $venvPy -m pip install --upgrade pip
    & $venvPy -m pip install -e ".\backend[dev]"
}

if (-not (Test-Path "data")) { New-Item -ItemType Directory data | Out-Null }

# Backend (embedded worker + auto-migrate against SQLite by default).
Write-Host "Starting API at http://localhost:8000 ..." -ForegroundColor Green
$api = Start-Process -PassThru -NoNewWindow $venvPy `
    -ArgumentList "-m", "uvicorn", "app.main:app", "--app-dir", "backend", "--host", "0.0.0.0", "--port", "8000"

# Frontend (only if it has been scaffolded yet).
if (Test-Path "frontend\package.json") {
    if (-not (Test-Path "frontend\node_modules")) {
        Write-Host "Installing frontend dependencies..." -ForegroundColor Cyan
        Push-Location frontend; npm install; Pop-Location
    }
    Write-Host "Starting web at http://localhost:3000 ..." -ForegroundColor Green
    Push-Location frontend
    try { npm run dev } finally { Pop-Location; Stop-Process -Id $api.Id -ErrorAction SilentlyContinue }
} else {
    Write-Host "Frontend not scaffolded yet; API only. Ctrl+C to stop." -ForegroundColor Yellow
    Wait-Process -Id $api.Id
}
