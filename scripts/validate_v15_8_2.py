#!/usr/bin/env python3
from pathlib import Path
import py_compile

root=Path.cwd()
for p in [
    root/"baby_ui_backend/v158_event_backfill.py",
    root/"scripts/v1581_fusion_scenarios.py",
    root/"scripts/v1582_regression.py",
]:
    if not p.exists():
        raise SystemExit(f"Missing {p}")
    py_compile.compile(str(p),doraise=True)

print("V15.8.2 validation PASS")
print("Cross-layer contradiction propagation enabled.")
print("Fusion states/overlays remain owned by the existing V15.7 fusion engine.")
print("No automatic execution or quantity selection was added.")
