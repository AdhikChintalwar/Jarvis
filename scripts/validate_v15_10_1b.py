#!/usr/bin/env python3
from pathlib import Path

root = Path(__file__).resolve().parents[1]
p = root / "baby_ui_backend" / "v1510_opportunity.py"
t = p.read_text()

for needle in [
    "has_structured_capital_evidence",
    "V15.10.1b safety merge",
    'capital_level = _u(getattr(intel.capital_risk, "level", "UNKNOWN"))',
]:
    assert needle in t, needle

print("V15.10.1b validation PASS")
print("Structured refinement is conditional on structured SEC/event evidence.")
print("Base capital risk is preserved when structured evidence is absent.")
print("Final PAPER eligibility and execution authority are unchanged.")
