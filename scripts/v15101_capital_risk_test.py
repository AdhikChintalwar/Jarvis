#!/usr/bin/env python3
from baby_ui_backend.v15101_capital_risk import evaluate_structured_capital_risk

def report(gc=None, offering=None, events=None):
    return {
        "raw": {
            "production_result": {
                "deep_sec": {
                    "going_concern_flags": gc or [],
                    "offering_flags": offering or [],
                },
                "event_intelligence": {"events": events or []},
            }
        }
    }

r = report(
    gc=[{
        "phrase": "substantial doubt about going concern",
        "context": "As previously disclosed, there was substantial doubt. Subsequent transactions repaid the term loans and removed the substantial doubt noted."
    }],
    offering=[{
        "category": "offering",
        "phrase": "at-the-market offering",
        "context": "sales may be made in at the market offerings under Rule 415 pursuant to this prospectus"
    }],
    events=[{
        "event_type": "sec_offering:REGISTRATION",
        "title": "at-the-market offering",
        "notes": [
            "Registration/prospectus context detected.",
            "Registration/prospectus filing does not by itself prove securities were issued or dilution occurred."
        ]
    }]
)
x = evaluate_structured_capital_risk(r)
assert x.level == "MODERATE", x
print("PASS resolved_gc_plus_registration_is_moderate")

r = report(gc=[{
    "phrase": "substantial doubt about going concern",
    "context": "These conditions raise substantial doubt about the company's ability to continue as a going concern."
}])
x = evaluate_structured_capital_risk(r)
assert x.level == "HIGH", x
print("PASS unresolved_gc_is_high")

r = report(
    offering=[{"phrase": "at-the-market offering", "context": "prospectus registration under Rule 415"}],
    events=[{
        "event_type": "sec_offering:REGISTRATION",
        "notes": ["Registration/prospectus filing does not by itself prove securities were issued or dilution occurred."]
    }]
)
x = evaluate_structured_capital_risk(r)
assert x.level == "MODERATE", x
print("PASS registration_only_is_moderate")

x = evaluate_structured_capital_risk(report())
assert x.level == "LOW", x
print("PASS no_structured_risk_is_low")

print("V15.10.1 structured-capital-risk tests PASS")
