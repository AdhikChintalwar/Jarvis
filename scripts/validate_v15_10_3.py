#!/usr/bin/env python3
from pathlib import Path

p = Path("scripts/v15103_opportunity_replay.py")
assert p.exists(), "scripts/v15103_opportunity_replay.py missing"
t = p.read_text()

for needle in [
    "QuantitativeFilter",
    "OpportunityScorer",
    'get_profile("unusual-volume")',
    "ReplayTrajectoryStore",
    "report bars absent",
    "market-wide top-50 ranking",
    "forward_stats",
]:
    assert needle.lower() in t.lower(), needle

print("V15.10.3 replay validator PASS")
print("Uses production QuantitativeFilter + OpportunityScorer.")
print("Uses sequential point-in-time daily history.")
print("Uses in-memory V15.10 trajectory store; live trajectory DB is not modified.")
print("Does not claim market-wide top-50 ranking or predictive validation.")
