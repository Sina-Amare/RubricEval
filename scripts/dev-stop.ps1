# Stop the RubricEval stack: our tracked PIDs plus the two dev ports.
# Usage:  .\scripts\dev-stop.ps1            (frees 8000 + 3000)
#         .\scripts\dev-stop.ps1 -Port 8090 (if you started with -Port 8090)
param([int]$Port = 8000)
$root = Split-Path -Parent $PSScriptRoot
$pidFile = Join-Path $root ".dev-pids"
if (Test-Path $pidFile) {
  Get-Content $pidFile | ForEach-Object {
    if ($_ -match '^\d+$') {
      try { Stop-Process -Id ([int]$_) -Force -ErrorAction Stop } catch {}
    }
  }
  Remove-Item $pidFile -ErrorAction SilentlyContinue
}
# Also free our ports in case a child (node) was orphaned by the cmd wrapper.
foreach ($p in $Port, 3000) {
  try {
    $owners = (Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction Stop).OwningProcess |
      Select-Object -Unique
    foreach ($o in $owners) { if ($o -gt 0) { Stop-Process -Id ([int]$o) -Force -ErrorAction SilentlyContinue } }
  } catch {}
}
Write-Host "RubricEval stopped (PIDs + ports $Port/3000 freed)."
