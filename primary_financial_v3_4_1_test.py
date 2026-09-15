from investor.primary_data import PrimaryFinancialEngine

for ticker in ("AAPL", "SLDE", "CRWD"):
    print("\n" + "=" * 88)
    print("V3.4.1", ticker)
    print("=" * 88)

    report = PrimaryFinancialEngine().analyze_company(ticker)
    cv = report.get("cross_validation") or {}

    for metric in ("capex", "free_cash_flow"):
        x = (cv.get("metrics") or {}).get(metric, {})
        print(
            metric,
            "| SEC:", x.get("primary_value"),
            "| Yahoo:", x.get("secondary_value"),
            "| period:", x.get("period_status"),
            "| semantic:", x.get("semantic_status"),
            "| status:", x.get("status"),
            "| confidence:", x.get("confidence"),
        )

    verified = report.get("verified_financials", {})
    for metric in ("capex", "free_cash_flow"):
        x = verified.get(metric, {})
        print(
            "VERIFIED", metric,
            "| value:", x.get("value"),
            "| source:", x.get("source"),
            "| status:", x.get("status"),
        )
