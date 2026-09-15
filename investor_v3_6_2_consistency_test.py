from types import SimpleNamespace
from investor.financial_engine import FinancialEngine
from investor.financial_evidence import (
    FinancialEvidenceContext,
    CANONICAL_FINANCIAL_EVIDENCE_METRICS,
)

def item(value, status, confidence):
    return {"value": value, "status": status, "confidence": confidence}

primary = {"verified_financials": {
    "revenue_growth_yoy": item(.365, "PRIMARY_ONLY", .85),
    "net_margin": item(.384, "STRONG_AGREEMENT", .97),
    "operating_margin": item(None, "MISSING", 0),
    "free_cash_flow": item(794_575_000, "STRONG_AGREEMENT", .97),
    "operating_cash_flow": item(797_432_000, "STRONG_AGREEMENT", .97),
    "cash": item(1_236_915_000, "PERIOD_MISMATCH", .70),
    "debt": item(29_703_000, "PERIOD_MISMATCH", .70),
}}

f = SimpleNamespace(
    revenue_growth=.365,
    profit_margin=.384,
    operating_margin=None,
    free_cash_flow=794_575_000,
    operating_cash_flow=797_432_000,
    total_cash=1_236_915_000,
    total_debt=29_703_000,
)

canonical = FinancialEvidenceContext(primary).summarize(
    CANONICAL_FINANCIAL_EVIDENCE_METRICS
)
health = FinancialEngine().analyze(f, primary)

assert round(canonical["coverage"] * 100, 2) == 85.71
assert "operating_margin" in canonical["gated"]
assert health.evidence_coverage == round(canonical["coverage"] * 100, 2)
assert health.evidence_confidence == round(canonical["confidence"] * 100, 2)
assert health.gated_metrics == canonical["gated"]

print("V3.6.2 canonical financial evidence consistency: PASS")
print("confidence:", health.evidence_confidence)
print("coverage:", health.evidence_coverage)
print("gated:", health.gated_metrics)
