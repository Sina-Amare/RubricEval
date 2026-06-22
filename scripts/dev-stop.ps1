# Stop the RubricEval stack. Only touches our PIDs + our two ports (8090, 3000).
# Never affects other projects (e.g. scrapegpt on 8000/5050).
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
# Also free our two ports in case a child (node) was orphaned by the cmd wrapper.
foreach ($port in 8090, 3000) {
  try {
    $owners = (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction Stop).OwningProcess |
      Select-Object -Unique
    foreach ($o in $owners) { if ($o -gt 0) { Stop-Process -Id ([int]$o) -Force -ErrorAction SilentlyContinue } }
  } catch {}
}
Write-Host "RubricEval stopped (PIDs + ports 8090/3000 freed)."
