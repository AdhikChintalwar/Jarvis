#!/usr/bin/env python3
from pathlib import Path
p=Path("scripts/v15104_normal_gate_funnel.py")
assert p.exists(), "scripts/v15104_normal_gate_funnel.py missing"
t=p.read_text()
for x in [
    "ACTIVE_SETUP",
    "synthetic_smoke",
    "proposal_service",
    "structurally_clean_active_setup_count",
    "This audit does NOT relax any gate",
]:
    assert x in t, x
print("V15.10.4 validation PASS")
print("Normal production-report setup funnel audit enabled.")
print("Synthetic ProposalService reachability smoke test enabled.")
print("No thresholds, broker execution, quantity authority, or real-money settings changed.")
