#!/usr/bin/env bash
set -euo pipefail

echo "== service =="
sudo systemctl --no-pager status baby-api || true

echo
echo "== local API =="
curl -fsS http://127.0.0.1:8787/api/production/health | python3 -m json.tool

echo
echo "== scheduler =="
curl -fsS http://127.0.0.1:8787/api/scheduler/status | python3 -m json.tool

echo
echo "== monitor jobs =="
curl -fsS http://127.0.0.1:8787/api/monitor/jobs | python3 -m json.tool
