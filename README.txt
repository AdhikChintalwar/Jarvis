BABY INVESTOR V3.5 — PRIMARY FINANCIAL INTEGRATION
==================================================

This package was built against the investor/ source tree uploaded on 2026-09-15.

WHAT CHANGES
------------
1. StockAnalyzer now runs PrimaryFinancialEngine before classification,
   financial-health scoring, and stock scoring.
2. Statement-derived Yahoo .info fundamentals are replaced by SEC-primary
   verified values:
      revenue
      revenue growth
      net income
      net margin
      operating margin
      cash
      debt
      free cash flow
      operating cash flow
3. Missing or MATERIAL_DISAGREEMENT primary facts stay missing. The analyzer
   does not revive an old Yahoo .info value for that metric.
4. Yahoo remains the prototype source for market data, valuation fields,
   beta, float/short data, etc.
5. The full verified-financial provenance is attached to the analyzer report
   as report["primary_financial"].
6. Committee EvidenceBuilder carries compact value/source/status/confidence/
   period records into Nemotron evidence.
7. EvidenceRegistry treats primary_financial as high-reliability SEC-primary
   evidence.
8. Primary financial schema is bumped to 3.5.

INSTALL
-------
From the project root, copy the package files over the same relative paths.

TEST
----
python -m py_compile \
  investor/analyzer.py \
  investor/primary_data/integration_adapter.py \
  investor/primary_data/primary_financial_engine.py \
  investor/committee/evidence_builder.py \
  investor/integrity/evidence_registry.py \
  investor_v3_5_integration_test.py

python investor_v3_5_integration_test.py

Then run real deterministic analysis:
python - <<'PY'
from investor.analyzer import StockAnalyzer

for ticker in ("AAPL", "SLDE", "CRWD"):
    print("\n", "=" * 30, ticker, "=" * 30)
    report = StockAnalyzer().analyze(ticker)
    pf = report.get("primary_financial") or {}
    verified = pf.get("verified_financials", {})
    print("schema:", pf.get("schema_version"))
    for metric in (
        "revenue", "revenue_growth_yoy", "net_margin",
        "operating_cash_flow", "capex", "free_cash_flow",
        "cash", "debt", "shares_change_yoy",
    ):
        x = verified.get(metric, {})
        print(
            metric,
            "|", x.get("value"),
            "|", x.get("source"),
            "|", x.get("status"),
            "| conf", x.get("confidence"),
            "|", x.get("period"),
        )
    print("fundamental score:", report["score"].overall_score)
    print("financial health:", report["financial_health"].score)
PY

EXPECTED CRWD SAFETY BEHAVIOR
-----------------------------
- capex stays unresolved if V3.4.1 reports MATERIAL_DISAGREEMENT.
- free_cash_flow may remain SEC_XBRL / REVIEW.
- cash and debt may remain SEC_XBRL / PERIOD_MISMATCH because Yahoo annual
  balance-sheet data is older.
- shares_change_yoy remains missing while the SEC share series is quarantined.
- Nemotron evidence receives these statuses and confidence values.

GIT — ONLY AFTER REAL TESTS PASS
--------------------------------
git status
git add \
  investor/analyzer.py \
  investor/primary_data/integration_adapter.py \
  investor/primary_data/primary_financial_engine.py \
  investor/committee/evidence_builder.py \
  investor/integrity/evidence_registry.py \
  investor_v3_5_integration_test.py

git commit -m "feat(investor): integrate verified primary financials into analysis pipeline"

git tag -a investor-v3.5 \
  -m "Baby Investor V3.5 primary financial integration"

git log --oneline --decorate -8

Do not push until AAPL, SLDE, and CRWD real-analysis output is reviewed.
