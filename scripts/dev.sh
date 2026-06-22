#!/usr/bin/env bash
# Local development launcher (macOS/Linux, no Docker required).
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env from .env.example — set OPENROUTER_API_KEY/OPERATOR_TOKEN."
fi

VPY="backend/.venv/bin/python"
if [ ! -x "$VPY" ]; then
  echo "Creating backend virtualenv..."
  ${PY:-python3} -m venv backend/.venv
  "$VPY" -m pip install --upgrade pip
  "$VPY" -m pip install -e "./backend[dev]"
fi

mkdir -p data

echo "Starting API at http://localhost:8000 ..."
"$VPY" -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000 &
API_PID=$!
trap 'kill $API_PID 2>/dev/null || true' EXIT

if [ -f frontend/package.json ]; then
  [ -d frontend/node_modules ] || (cd frontend && npm install)
  echo "Starting web at http://localhost:3000 ..."
  (cd frontend && npm run dev)
else
  echo "Frontend not scaffolded yet; API only. Ctrl+C to stop."
  wait $API_PID
fi
