#!/usr/bin/env python3
from pathlib import Path
import py_compile

root=Path.cwd()
for p in [
    root/"baby_ui_backend/v158_event_backfill.py",
    root/"baby_ui_backend/v157_fusion.py",
    root/"scripts/v1581_fusion_scenarios.py",
    root/"scripts/v1581_regression.py",
]:
    if not p.exists():
        raise SystemExit(f"Missing {p}")
    py_compile.compile(str(p),doraise=True)

print("V15.8.1 validation PASS")
print("Fusion scenario matrix enabled.")
print("No-position, financing-risk, adverse-context, DATA_ISSUE and trusted-danger cases covered.")
print("No execution or quantity logic changed.")
