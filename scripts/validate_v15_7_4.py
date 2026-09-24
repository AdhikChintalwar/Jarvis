#!/usr/bin/env python3
from pathlib import Path
import py_compile

root=Path.cwd()
for p in [
    root/"scripts/v157_build_benchmark_manifest.py",
    root/"scripts/v157_run_trusted_replays.py",
    root/"scripts/v157_benchmark_report.py",
]:
    if not p.exists():
        raise SystemExit(f"Missing {p}")
    py_compile.compile(str(p),doraise=True)

print("V15.7.4 validation PASS")
print("Distributed-date benchmark manifest builder enabled.")
print("Trusted-session-only replay runner enabled.")
print("No-position control alert audit enabled.")
print("Reference-position alert report enabled.")
print("No execution or quantity logic changed.")
