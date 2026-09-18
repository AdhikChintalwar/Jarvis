#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/opt/baby"
BACKUP_DIR="/opt/baby-backups"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"

mkdir -p "$BACKUP_DIR"

backup_db() {
  local db="$1"
  if [ -f "$db" ]; then
    local base
    base="$(basename "$db")"
    sqlite3 "$db" ".backup '$BACKUP_DIR/${base}.${STAMP}.sqlite'"
  fi
}

backup_db "$PROJECT_DIR/data/baby_investment_monitor.db"
backup_db "$PROJECT_DIR/data/baby_production.db"

find "$BACKUP_DIR" -type f -mtime +14 -delete

echo "Baby SQLite backup complete: $STAMP"
