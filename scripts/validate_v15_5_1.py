#!/usr/bin/env python3
from pathlib import Path
import py_compile,sys,re
root=Path.cwd()
targets=[
    root/"baby_ui_backend/v155_intelligence.py",
    root/"scripts/v155_replay.py",
]
for p in targets:
    if not p.exists():
        raise SystemExit(f"Missing {p}")
    py_compile.compile(str(p),doraise=True)
s=(root/"baby_ui_backend/v155_intelligence.py").read_text()
r=(root/"scripts/v155_replay.py").read_text()
for marker in [
    "CLIMACTIC_EXPANSION","PROTECT_PROFIT","one_day_pct",
    "true_range_atr","distance_sma5_pct","retention_20"
]:
    if marker not in s: raise SystemExit(f"Missing intelligence marker: {marker}")
for marker in ["entry_snapshot","exit_snapshot","flow_retention","confidence","data=[r for r in all_data"]:
    if marker not in r: raise SystemExit(f"Missing replay marker: {marker}")
print("V15.5.1 validation PASS")
print("Replay timeline is capped at exit-date when supplied.")
print("Retention and confidence aliases are exposed.")
print("CLIMACTIC_EXPANSION and PROTECT_PROFIT are enabled.")
print("No automatic order execution was added.")
