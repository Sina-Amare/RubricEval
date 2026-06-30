# Run the frontend E2E suite against a throwaway FakeLLM backend (no API key).
#   .\scripts\e2e.ps1
# Starts the API (LLM_BACKEND=fake) on :8000, builds + serves the web app via
# Playwright's webServer, runs the suite, then tears the API down.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$py = Join-Path $root "backend\.venv\Scripts\python.exe"
$token = "e2e-token"   # must match e2e/full-flow.spec.ts default

if (-not (Test-Path $py)) {
  Write-Host "Backend venv missing. Run once: py -3.11 -m venv backend\.venv; backend\.venv\Scripts\pip install -e `".\backend[dev]`"" -ForegroundColor Yellow
  exit 1
}

$env:LLM_BACKEND = "fake"
$env:OPERATOR_TOKEN = $token
$env:APP_SECRET_KEY = "e2e-insecure-secret-key-32-characters-min"
$env:DATABASE_URL = "sqlite+aiosqlite:///./data/e2e.db"
$env:AUTO_MIGRATE = "true"
$env:NEXT_PUBLIC_API_BASE_URL = "http://localhost:8000"

$api = Start-Process -PassThru -WindowStyle Hidden -FilePath $py `
  -ArgumentList "-m", "uvicorn", "app.main:app", "--port", "8000" `
  -WorkingDirectory (Join-Path $root "backend")
try {
  # Wait for the API to answer /health before driving the UI against it.
  for ($i = 0; $i -lt 40; $i++) {
    try {
      if ((Invoke-WebRequest -UseBasicParsing http://localhost:8000/api/health -TimeoutSec 2).StatusCode -eq 200) { break }
    } catch { Start-Sleep -Seconds 1 }
  }
  Push-Location (Join-Path $root "frontend")
  try {
    if (-not (Test-Path "node_modules")) { npm install }
    npm run build
    npx playwright test
  } finally {
    Pop-Location
  }
} finally {
  Stop-Process -Id $api.Id -Force -ErrorAction SilentlyContinue
}
