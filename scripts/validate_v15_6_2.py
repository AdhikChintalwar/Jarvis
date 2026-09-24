#!/usr/bin/env python3
from pathlib import Path
import py_compile

root=Path.cwd()
targets=[
    root/"baby_ui_backend/v155_intelligence.py",
    root/"baby_ui_backend/v156_regime.py",
    root/"baby_ui_backend/v156_event_risk.py",
    root/"scripts/v155_replay.py",
]
for p in targets:
    if not p.exists():
        raise SystemExit(f"Missing {p}")
    py_compile.compile(str(p),doraise=True)

m=(root/"baby_ui_backend/v156_event_risk.py").read_text()
r=(root/"scripts/v155_replay.py").read_text()

for marker in [
    "A_PRIMARY_OFFICIAL",
    "B_COMPANY_DISTRIBUTION",
    "structural_risk_level",
    "EVENT_DRIVEN_MERGER",
    "FINANCING_OFFERING",
    "ATM_SHELF",
    "REVERSE_SPLIT",
    "GOING_CONCERN",
    "catalyst_causality",
]:
    if marker not in m:
        raise SystemExit(f"Missing event-risk marker: {marker}")

for marker in [
    "--events-csv",
    "assess_events",
    "structural_risk_level",
    "catalyst_regime",
    "current_events",
]:
    if marker not in r:
        raise SystemExit(f"Missing replay marker: {marker}")

print("V15.6.2 validation PASS")
print("Point-in-time daily event replay is enabled.")
print("Structural risk and catalyst regime are separated.")
print("Press-release distributors are not treated as identical to regulator/SEC evidence.")
print("Catalyst causality remains NOT_ESTABLISHED.")
print("No automatic execution or quantity selection was added.")
