#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/opt/baby"

echo "== Baby backend install =="

sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-pip git sqlite3 curl

if [ ! -d "$PROJECT_DIR" ]; then
  echo "Create or clone Baby into $PROJECT_DIR before continuing."
  exit 1
fi

cd "$PROJECT_DIR"

python3 -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip

if [ -f requirements.txt ]; then
  pip install -r requirements.txt
else
  echo "requirements.txt not found."
  echo "Create it from the local Baby environment before deployment."
  exit 1
fi

sudo cp deploy/oracle/baby-api.service /etc/systemd/system/baby-api.service
sudo systemctl daemon-reload
sudo systemctl enable baby-api

echo
echo "NEXT:"
echo "1. Create /opt/baby/.env"
echo "2. sudo systemctl start baby-api"
echo "3. sudo systemctl status baby-api"
