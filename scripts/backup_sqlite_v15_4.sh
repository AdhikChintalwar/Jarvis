#!/usr/bin/env bash
set -euo pipefail

BABY_ROOT="${BABY_ROOT:-/opt/baby}"
DATA_DIR="${BABY_DATA_DIR:-$BABY_ROOT/data}"
BACKUP_ROOT="${BABY_BACKUP_ROOT:-/opt/baby-backups}"
RETENTION_DAYS="${BABY_BACKUP_RETENTION_DAYS:-14}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DEST="$BACKUP_ROOT/$STAMP"

mkdir -p "$DEST/databases" "$DEST/files"

python3 - "$DATA_DIR" "$DEST/databases" <<'PY'
import sqlite3,sys
from pathlib import Path
src=Path(sys.argv[1]); dst=Path(sys.argv[2])
for p in sorted(src.rglob("*.db")):
    target=dst/p.relative_to(src)
    target.parent.mkdir(parents=True,exist_ok=True)
    s=sqlite3.connect(f"file:{p}?mode=ro",uri=True)
    d=sqlite3.connect(target)
    try:
        s.backup(d)
    finally:
        d.close(); s.close()
    print("sqlite backup:",p,"->",target)
PY

python3 - "$DATA_DIR" "$DEST/files" <<'PY'
import shutil,sys
from pathlib import Path
src=Path(sys.argv[1]); dst=Path(sys.argv[2])
for p in src.rglob("*"):
    if not p.is_file() or p.suffix==".db" or "__pycache__" in p.parts or p.name.endswith(".tmp"):
        continue
    target=dst/p.relative_to(src)
    target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(p,target)
PY

python3 - "$DEST" <<'PY'
import hashlib,json,sys
from pathlib import Path
root=Path(sys.argv[1]); rows=[]
for p in sorted(root.rglob("*")):
    if not p.is_file() or p.name in {"MANIFEST.json","SHA256SUMS"}:
        continue
    h=hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""):
            h.update(chunk)
    rows.append({"path":str(p.relative_to(root)),"sha256":h.hexdigest(),"bytes":p.stat().st_size})
(root/"MANIFEST.json").write_text(json.dumps({"file_count":len(rows),"files":rows},indent=2))
(root/"SHA256SUMS").write_text("\n".join(f"{x['sha256']}  {x['path']}" for x in rows)+"\n")
PY

python3 - "$DEST/databases" <<'PY'
import sqlite3,sys
from pathlib import Path
for p in Path(sys.argv[1]).rglob("*.db"):
    with sqlite3.connect(p) as db:
        result=db.execute("PRAGMA quick_check").fetchone()
    if not result or result[0]!="ok":
        raise SystemExit(f"SQLite quick_check failed: {p}: {result}")
print("SQLite quick_check PASS")
PY

find "$BACKUP_ROOT" -mindepth 1 -maxdepth 1 -type d -mtime +"$RETENTION_DAYS" -print -exec rm -rf {} +

echo "Baby backup complete: $DEST"

if [[ -n "${BABY_BACKUP_REMOTE:-}" ]]; then
  command -v rclone >/dev/null || { echo "rclone required for BABY_BACKUP_REMOTE" >&2; exit 2; }
  rclone copy "$DEST" "${BABY_BACKUP_REMOTE%/}/$STAMP"
  echo "Off-VM backup copied to ${BABY_BACKUP_REMOTE%/}/$STAMP"
fi
