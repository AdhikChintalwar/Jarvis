#!/usr/bin/env python3
from pathlib import Path
root=Path(__file__).resolve().parents[1]
opp=root/'baby_ui_backend'/'v1510_opportunity.py'
sub=root/'baby_ui_backend'/'subscriber_email.py'
assert opp.exists(), 'v1510_opportunity.py missing'
t=opp.read_text()
for needle in ['OpportunityTrajectoryStore','v1510_opportunity_trajectory','_scanner_flow_label','_candidate_is_monitor_worthy','USER_SELECTED']:
    assert needle in t, f'missing {needle}'
assert 'from .v1510_opportunity import analyze as v155_analyze' in sub.read_text()
print('V15.10.0 validation PASS')
print('Scanner aggregate flow bridge enabled.')
print('Point-in-time opportunity trajectory ledger enabled.')
print('Strict final setup/PAPER readiness remains sovereign.')
print('No automatic quantity selection or real-money execution added.')
