from investor.models import FundamentalMetrics
from investor.primary_data.integration_adapter import PrimaryFinancialIntegrationAdapter
from investor.analyzer import StockAnalyzer
from investor.committee.evidence_builder import EvidenceBuilder
from investor.integrity.evidence_registry import EvidenceRegistry


def fake_verified(value, status="STRONG_AGREEMENT", confidence=.97, period="2026-01-31"):
    return {
        "value": value,
        "source": "SEC_XBRL" if value is not None else "unresolved",
        "status": status,
        "confidence": confidence,
        "period": period,
        "evidence": {},
    }


report = {
    "schema_version": "3.5",
    "primary_source": "SEC EDGAR Company Facts / XBRL",
    "secondary_source": "Yahoo Finance annual statements",
    "verified_financials": {
        "revenue": fake_verified(4_812_005_000),
        "revenue_growth_yoy": fake_verified(.217112),
        "gross_margin": fake_verified(.74669),
        "operating_margin": fake_verified(-.06095),
        "net_margin": fake_verified(-.03377),
        "net_income": fake_verified(-162_502_000),
        "operating_cash_flow": fake_verified(1_612_349_000),
        "free_cash_flow": fake_verified(1_310_241_000, "REVIEW", .72),
        "cash": fake_verified(5_013_847_000, "PERIOD_MISMATCH", .70, "2026-07-31"),
        "debt": fake_verified(746_216_000, "PERIOD_MISMATCH", .70, "2026-07-31"),
        "capex": fake_verified(None, "MATERIAL_DISAGREEMENT", .25),
        "shares_change_yoy": fake_verified(None, "MISSING", 0.0, "2026-08-20"),
    },
    "balance_sheet_snapshot": {
        "anchor_date": "2026-07-31",
        "confidence": .835,
        "status": "coherent_current",
        "freshness_days": 0,
        "core_coverage": 5,
        "optional_coverage": 0,
    },
}

payload = PrimaryFinancialIntegrationAdapter().to_financial_engine_payload(report)

f = FundamentalMetrics(
    revenue=999,
    revenue_growth=999,
    net_income=999,
    profit_margin=999,
    operating_margin=999,
    total_cash=999,
    total_debt=999,
    free_cash_flow=999,
    operating_cash_flow=999,
)

# Avoid constructing StockAnalyzer because that initializes network-facing engines.
StockAnalyzer._apply_primary_financials(None, f, payload)

assert f.revenue == 4_812_005_000
assert f.revenue_growth == .217112
assert f.net_income == -162_502_000
assert f.profit_margin == -.03377
assert f.operating_margin == -.06095
assert f.total_cash == 5_013_847_000
assert f.total_debt == 746_216_000
assert f.free_cash_flow == 1_310_241_000
assert f.operating_cash_flow == 1_612_349_000

class Candidate:
    symbol = "CRWD"
    opportunity_score = 70
    flow_score = 60
    flow_type = "test"
    relative_volume = 1.5
    volume_zscore = 1.0
    daily_change_pct = 1.0
    gap_pct = 0.0
    close_location_pct = 75
    breakout_20d = False
    breakdown_20d = False
    flags = []

committee_evidence = EvidenceBuilder().build(
    Candidate(),
    {
        "ticker": "CRWD",
        "company_name": "CrowdStrike",
        "generated_at": "2026-09-15T00:00:00",
        "fundamentals": f,
        "primary_financial": report,
    },
)

assert "primary_financial" in committee_evidence
assert committee_evidence["primary_financial"]["verified_financials"]["revenue"]["source"] == "SEC_XBRL"
assert committee_evidence["primary_financial"]["verified_financials"]["capex"]["status"] == "MATERIAL_DISAGREEMENT"
assert committee_evidence["primary_financial"]["verified_financials"]["capex"]["value"] is None

registry = EvidenceRegistry().build(
    committee_evidence,
    generated_at="2026-09-15T00:00:00",
)

key = "primary_financial.verified_financials.revenue.value"
assert key in registry
assert registry[key].reliability == "high"
assert "SEC EDGAR/XBRL" in registry[key].source

print("V3.5 integration contract: PASS")
print("Verified SEC financials replace Yahoo statement fundamentals: PASS")
print("Unresolved primary facts remain unresolved in committee evidence: PASS")
print("Primary financial evidence registry reliability: HIGH")
