from investor.analyzer import StockAnalyzer

EXPECTED_FINANCIAL_AUTHORITY = {
    "AAPL": (87.57, 100.0),
    "SLDE": (73.71, 85.71),
    "CRWD": (84.0, 100.0),
}

for ticker in ("AAPL", "SLDE", "CRWD"):
    print("\n" + "=" * 100)
    print("V4.2.1 REAL ANALYSIS:", ticker)
    print("=" * 100)

    try:
        report = StockAnalyzer().analyze(ticker)
        r = report["unified_risk"]
        liq = report.get("liquidity_evidence", {})
        fd = r.dimensions["financial"]
        ld = r.dimensions["liquidity"]

        print("Unified risk score      :", r.risk_score)
        print("Risk level              :", r.risk_level)
        print("Confidence              :", r.confidence)
        print("Coverage                :", r.coverage)
        print("Position risk multiplier:", r.position_risk_multiplier)
        print("Hard overrides          :", r.hard_overrides)
        print("Unknowns                :", r.unknowns)

        print("\nFINANCIAL AUTHORITY")
        print("Financial risk score    :", fd.get("score"))
        print("Financial confidence    :", fd.get("confidence"))
        print("Financial coverage      :", fd.get("coverage"))
        print("Expected conf/coverage  :", EXPECTED_FINANCIAL_AUTHORITY[ticker])

        print("\nLIQUIDITY")
        print("ADV20 dollars           :", liq.get("average_dollar_volume_20d"))
        print("ADV20 shares            :", liq.get("average_share_volume_20d"))
        print("Sessions                :", liq.get("sessions"))
        print("As of                   :", liq.get("as_of"))
        print("Source                  :", liq.get("source"))
        print("Liquidity risk score    :", ld.get("score"))
        print("Liquidity state         :", ld.get("state"))
        print("Liquidity hard override :", ld.get("hard_override"))

        print("\nDIMENSIONS")
        for name, d in r.dimensions.items():
            print(
                f"  {name:20} score={d.get('score')} "
                f"state={d.get('state')} "
                f"conf={d.get('confidence')} "
                f"coverage={d.get('coverage')} "
                f"hard={d.get('hard_override')}"
            )

        print("\nStock score             :", report["score"].overall_score)

        expected_conf, expected_cov = EXPECTED_FINANCIAL_AUTHORITY[ticker]
        assert abs(fd.get("confidence", 0) - expected_conf) < 0.2
        assert abs(fd.get("coverage", 0) - expected_cov) < 0.2
        assert liq.get("average_dollar_volume_20d") is not None
        assert ld.get("score") is not None

        if ticker == "CRWD":
            assert r.risk_score >= 80
            assert r.hard_overrides

        print("RESULT: PASS")

    except Exception as error:
        print("RESULT: FAILED", type(error).__name__, error)
