#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
if [[ -f .venv/bin/activate ]]; then source .venv/bin/activate; fi
mkdir -p data/logs
python -m uvicorn baby_ui_backend.app:app --host 127.0.0.1 --port 8787 > data/logs/baby-ui-api.log 2>&1 &
API_PID=$!
cleanup(){ kill "$API_PID" 2>/dev/null || true; }
trap cleanup EXIT INT TERM
for i in {1..30}; do
  if curl -fsS http://127.0.0.1:8787/api/health >/dev/null 2>&1; then break; fi
  if ! kill -0 "$API_PID" 2>/dev/null; then echo "BABY API failed. Log:"; cat data/logs/baby-ui-api.log; exit 1; fi
  sleep .4
done
if ! curl -fsS http://127.0.0.1:8787/api/health >/dev/null; then echo "BABY API did not become healthy. Log:"; cat data/logs/baby-ui-api.log; exit 1; fi
echo "BABY API healthy: http://127.0.0.1:8787"
echo "API log: data/logs/baby-ui-api.log"
cd frontend
[[ -d node_modules ]] || npm install
npm run dev
