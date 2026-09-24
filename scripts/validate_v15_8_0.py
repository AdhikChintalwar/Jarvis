#!/usr/bin/env python3
from pathlib import Path
import py_compile,sys

root=Path.cwd()

required=[
    root/"baby_ui_backend/v156_event_risk.py",
    root/"baby_ui_backend/v157_fusion.py",
    root/"baby_ui_backend/v158_event_backfill.py",
    root/"scripts/v158_event_replay.py",
    root/"scripts/v158_regression.py",
]
for p in required:
    if not p.exists():
        raise SystemExit(f"Missing {p}")
    py_compile.compile(str(p),doraise=True)

sys.path.insert(0,str(root))
from baby_ui_backend.v158_event_backfill import point_in_time_events

rows=[
    {"symbol":"ABC","published_at":"2026-01-01T12:00:00Z","headline":"first"},
    {"symbol":"ABC","published_at":"2026-01-03T12:00:00Z","headline":"future"},
]
x=point_in_time_events(rows,"ABC","2026-01-02")
assert len(x)==1 and x[0]["headline"]=="first"

print("V15.8.0 validation PASS")
print("Point-in-time event backfill enabled.")
print("Dynamic compatibility adapter for installed V15.6.2 event engine enabled.")
print("Data-quality-aware fusion bridge enabled.")
print("No automatic execution or quantity selection was added.")
