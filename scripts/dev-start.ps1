# Start the RubricEval stack (backend + web) for local development.
#   Backend -> http://localhost:<Port>  (default 8000)
#   Web     -> http://localhost:3000
# Usage:  .\scripts\dev-start.ps1                 (default port 8000)
#         .\scripts\dev-start.ps1 -Port 8090      (if 8000 is taken)
#   Stop: .\scripts\dev-stop.ps1
param([int]$Port = 8000)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$py = Join-Path $root "backend\.venv\Scripts\python.exe"

if (-not (Test-Path $py)) {
  Write-Host "Backend venv missing. Run once:" -ForegroundColor Yellow
  Write-Host "  py -3.11 -m venv backend\.venv; backend\.venv\Scripts\pip install -e `".\backend[dev]`""
  exit 1
}

# The browser bundle must target the same port the API listens on (Next.js
# inlines NEXT_PUBLIC_* at build time), so point it there and rebuild whenever
# the cached .next was built for a different API URL. A sentinel records the URL
# the cache was built against, so the build is reused only when it still matches.
$env:NEXT_PUBLIC_API_BASE_URL = "http://localhost:$Port"
Push-Location (Join-Path $root "frontend")
if (-not (Test-Path "node_modules")) { npm install }
$sentinel = ".next\.api-url"
$built = if (Test-Path $sentinel) { (Get-Content $sentinel -Raw).Trim() } else { "" }
if ((-not (Test-Path ".next")) -or ($built -ne $env:NEXT_PUBLIC_API_BASE_URL)) {
  npm run build
  Set-Content $sentinel $env:NEXT_PUBLIC_API_BASE_URL
}
Pop-Location

$be = Start-Process -PassThru -WindowStyle Hidden -FilePath $py `
  -ArgumentList "-m", "uvicorn", "app.main:app", "--port", "$Port" `
  -WorkingDirectory (Join-Path $root "backend") `
  -RedirectStandardOutput (Join-Path $root ".dev-backend.log") `
  -RedirectStandardError (Join-Path $root ".dev-backend.err.log")

$fe = Start-Process -PassThru -WindowStyle Hidden -FilePath "cmd.exe" `
  -ArgumentList "/c", "npm run start" `
  -WorkingDirectory (Join-Path $root "frontend") `
  -RedirectStandardOutput (Join-Path $root ".dev-frontend.log") `
  -RedirectStandardError (Join-Path $root ".dev-frontend.err.log")

"$($be.Id)`n$($fe.Id)" | Set-Content (Join-Path $root ".dev-pids")

Start-Sleep -Seconds 4
Write-Host ""
Write-Host "Backend started (PID $($be.Id)) -> http://localhost:$Port" -ForegroundColor Green
Write-Host "Web     started (PID $($fe.Id)) -> http://localhost:3000" -ForegroundColor Green
Write-Host ""
Write-Host "Open http://localhost:3000 and sign in with your OPERATOR_TOKEN (from backend\.env)."
Write-Host "Logs: .dev-backend.log / .dev-frontend.log    Stop: .\scripts\dev-stop.ps1"
