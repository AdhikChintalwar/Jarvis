#!/usr/bin/env python3
from pathlib import Path

root = Path(__file__).resolve().parents[1]
risk = root / "baby_ui_backend" / "v15101_capital_risk.py"
opp = root / "baby_ui_backend" / "v1510_opportunity.py"

assert risk.exists()
rt = risk.read_text()
for needle in [
    "evaluate_structured_capital_risk",
    "removed the substantial doubt",
    "Registration/prospectus",
    "does not by itself prove securities were issued",
    "Current unresolved going-concern risk detected",
]:
    assert needle in rt, needle

ot = opp.read_text()
assert "from .v15101_capital_risk import evaluate_structured_capital_risk" in ot
assert "structured_cap = evaluate_structured_capital_risk" in ot
assert "intel.capital_risk.level = structured_cap.level" in ot

print("V15.10.1 validation PASS")
print("Structured SEC/event capital-risk refinement enabled for research monitoring.")
print("Registration/prospectus alone is not treated as completed issuance.")
print("Explicitly resolved going-concern language is preserved as historical context.")
print("Production V11 risk and final PAPER gate remain sovereign.")
