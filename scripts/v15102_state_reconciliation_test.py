#!/usr/bin/env python3
from unittest.mock import patch

import baby_ui_backend.v1510_opportunity as o
from baby_ui_backend.v155_intelligence import Intelligence, Flow, Catalyst, CapitalRisk


def base_high():
    return Intelligence(
        symbol="TEST",
        stage="RESEARCH",
        phase="INSUFFICIENT_DATA",
        setup_state="BLOCKED",
        ready=False,
        setup_type="INSUFFICIENT_DATA",
        flow=Flow(label="INSUFFICIENT_DATA"),
        catalyst=Catalyst(),
        capital_risk=CapitalRisk("HIGH", [
            "Potential shelf/ATM financing overhang detected.",
            "Going-concern language detected.",
        ]),
        observed_facts=[
            "Scanner opportunity score: 80.",
            "Elevated positive-volume persistence: 0/5 sessions.",
        ],
        interpretation=[],
        contradicting_evidence=[
            "Potential shelf/ATM financing overhang detected.",
            "Going-concern language detected.",
        ],
        next_conditions=[
            "Advance only if price/flow confirmation improves without violating liquidity or quote-quality gates.",
            "Do not upgrade without resolving capital-structure/financing risk.",
        ],
        monitoring_signal="REVIEW",
        evidence_score=30,
        fingerprint="old",
    )


candidate = {
    "symbol": "TEST",
    "price": 10.0,
    "opportunity_score": 82,
    "flow_score": 90,
    "flow_type": "STRONG_ACCUMULATION",
    "relative_volume": 2.0,
    "rvol_3d_average": 2.2,
    "high_volume_days_5d": 3,
    "close_location_pct": 75,
    "current_dollar_volume": 20_000_000,
    "breakout_20d": True,
}

report = {
    "raw": {
        "production_result": {
            "deep_sec": {
                "going_concern_flags": [{
                    "phrase": "substantial doubt about going concern",
                    "context": "subsequent transactions removed the substantial doubt noted",
                }],
                "offering_flags": [{
                    "phrase": "at-the-market offering",
                    "context": "prospectus registration under Rule 415",
                }],
            },
            "event_intelligence": {
                "events": [{
                    "event_type": "sec_offering:REGISTRATION",
                    "notes": [
                        "Registration/prospectus filing does not by itself prove securities were issued or dilution occurred."
                    ],
                }]
            },
        }
    }
}


class MemStore:
    def __init__(self, *a, **k):
        pass
    def record(self, symbol, candidate):
        pass
    def recent(self, symbol, days=10):
        return []


with patch.object(o, "OpportunityTrajectoryStore", MemStore):
    with patch.object(o, "_base_analyze", lambda *a, **k: base_high()):
        x = o.analyze("TEST", candidate, report, {})

assert x.stage == "MONITOR", x
assert x.ready is False
assert x.capital_risk.level == "MODERATE", x.capital_risk
assert x.monitoring_signal == "CONTINUE", x.monitoring_signal
assert not any("Elevated positive-volume persistence: 0/5" in s for s in x.observed_facts)
assert any("Scanner high-volume persistence: 3/5" in s for s in x.observed_facts)
assert not any(s == "Going-concern language detected." for s in x.contradicting_evidence)
assert not any("Do not upgrade without resolving capital-structure" in s for s in x.next_conditions)
assert any("registration/ATM-capacity" in s for s in x.next_conditions)

print("PASS structured_risk_state_reconciliation")
print("V15.10.2 state-reconciliation tests PASS")
