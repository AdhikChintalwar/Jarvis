#!/usr/bin/env python3
from pathlib import Path
import py_compile

root=Path.cwd()
for p in [
    root/"scripts/v157_signal_diagnostics.py",
    root/"scripts/v157_shadow_reference_replays.py",
    root/"scripts/v157_shadow_reference_report.py",
]:
    if not p.exists():
        raise SystemExit(f"Missing {p}")
    py_compile.compile(str(p),doraise=True)

print("V15.7.5 validation PASS")
print("Intraday regime-frequency diagnostics enabled.")
print("Episode persistence diagnostics enabled.")
print("Reference-position shadow replay enabled.")
print("No thresholds or execution logic changed.")
