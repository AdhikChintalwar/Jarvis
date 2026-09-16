from investor.analyzer import StockAnalyzer

for ticker in ("AAPL", "SLDE", "CRWD"):
    print("\n" + "=" * 100)
    print("V4.2 REAL ANALYSIS:", ticker)
    print("=" * 100)

    try:
        report = StockAnalyzer().analyze(ticker)
        r = report["unified_risk"]

        print("Unified risk score     :", r.risk_score)
        print("Risk level             :", r.risk_level)
        print("Confidence             :", r.confidence)
        print("Coverage               :", r.coverage)
        print("Position risk multiplier:", r.position_risk_multiplier)
        print("Hard overrides         :", r.hard_overrides)
        print("Risk flags             :", r.risk_flags)
        print("Protective factors     :", r.protective_factors)
        print("Unknowns               :", r.unknowns)

        print("\nDIMENSIONS")
        for name, d in r.dimensions.items():
            print(
                f"  {name:20} score={d.get('score')} "
                f"state={d.get('state')} "
                f"conf={d.get('confidence')} "
                f"coverage={d.get('coverage')} "
                f"hard={d.get('hard_override')}"
            )
            for ev in d.get("evidence", []):
                print("    -", ev)

        print("\nAdvanced market        :", report["advanced_market"].market_structure)
        print("Macro regime           :", report["macro_regime"].regime)
        print("Stock score            :", report["score"].overall_score)
        print("RESULT: PASS")

    except Exception as error:
        print("RESULT: FAILED", type(error).__name__, error)
