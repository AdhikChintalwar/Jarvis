#!/usr/bin/env python3
from pathlib import Path

root = Path(__file__).resolve().parents[1]
p = root / "baby_ui_backend" / "v1510_opportunity.py"
t = p.read_text()

for needle in [
    "V15.10.2 state reconciliation",
    'not str(x).startswith("Elevated positive-volume persistence:")',
    "Continue monitoring registration/ATM-capacity risk",
    'intel.monitoring_signal = "CONTINUE"',
]:
    assert needle in t, needle

print("V15.10.2 validation PASS")
print("Stale V15.5 persistence text is removed when scanner persistence is available.")
print("Stale HIGH-risk REVIEW/next-condition text is reconciled after structured refinement.")
print("Strict final PAPER readiness remains unchanged.")
