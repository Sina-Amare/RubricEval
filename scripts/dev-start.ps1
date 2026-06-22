# Start the RubricEval stack on non-conflicting ports.
#   Backend  -> http://localhost:8090   (avoids scrapegpt's 8000)
#   Panel    -> http://localhost:3000
# Usage:  .\scripts\dev-start.ps1      Stop:  .\scripts\dev-stop.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$py = Join-Path $root "backend\.venv\Scripts\python.exe"

if (-not (Test-Path $py)) {
  Write-Host "Backend venv missing. Run once:" -ForegroundColor Yellow
  Write-Host "  py -3.11 -m venv backend\.venv; backend\.venv\Scripts\pip install -e `".\backend[dev]`""
  exit 1
}

# Ensure the frontend is built (first run only).
Push-Location (Join-Path $root "frontend")
if (-not (Test-Path "node_modules")) { npm install }
if (-not (Test-Path ".next")) { npm run build }
Pop-Location

$be = Start-Process -PassThru -WindowStyle Hidden -FilePath $py `
  -ArgumentList "-m", "uvicorn", "app.main:app", "--port", "8090" `
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
Write-Host "Backend  started (PID $($be.Id)) -> http://localhost:8090" -ForegroundColor Green
Write-Host "Panel    started (PID $($fe.Id)) -> http://localhost:3000" -ForegroundColor Green
Write-Host ""
Write-Host "Open http://localhost:3000   operator token: SINA0994"
Write-Host "Logs: .dev-backend.log / .dev-frontend.log"
Write-Host "Stop both: .\scripts\dev-stop.ps1"
