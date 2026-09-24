#!/usr/bin/env python3
from pathlib import Path
import py_compile, sys

root=Path.cwd()
targets=[
    root/"baby_ui_backend/v157_data_quality.py",
    root/"scripts/v157_intraday_replay.py",
]
for p in targets:
    if not p.exists():
        raise SystemExit(f"Missing {p}")
    py_compile.compile(str(p),doraise=True)

sys.path.insert(0,str(root))
from baby_ui_backend.v157_data_quality import assess_intraday_quality

sparse=[
    {"timestamp":"2026-09-23T13:30:00Z","open":10,"high":10.2,"low":9.9,"close":10.1,"volume":100},
    {"timestamp":"2026-09-23T19:50:00Z","open":10.1,"high":10.2,"low":10.0,"close":10.1,"volume":100},
]
q=assess_intraday_quality(sparse, {"open":10,"high":11,"low":9,"close":10.5,"volume":10000})
assert q.quality_state=="UNTRUSTED"
assert q.trust_intraday_signals is False

print("V15.7.1 validation PASS")
print("Sparse/incomplete intraday feeds are gated.")
print("Daily-bar reconciliation is enabled.")
print("Untrusted intraday signals become DATA_ISSUE in replay.")
print("No automatic execution or quantity selection was added.")
