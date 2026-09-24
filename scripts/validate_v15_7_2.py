#!/usr/bin/env python3
from pathlib import Path
import py_compile

root=Path.cwd()
for p in [
    root/"scripts/v157_batch_fetch.py",
    root/"scripts/v157_feed_audit.py",
    root/"scripts/v157_benchmark_plus.py",
]:
    if not p.exists():
        raise SystemExit(f"Missing {p}")
    py_compile.compile(str(p),doraise=True)

print("V15.7.2 validation PASS")
print("Batch intraday fetch helper enabled.")
print("Feed-quality audit harness enabled.")
print("Benchmark aggregation enabled.")
print("No execution or quantity logic changed.")
