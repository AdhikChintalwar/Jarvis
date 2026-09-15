from investor.analyzer import StockAnalyzer

for ticker in ("AAPL", "SLDE", "CRWD"):
    print("\n" + "=" * 100)
    print("V4.1 REAL ANALYSIS:", ticker)
    print("=" * 100)

    try:
        report = StockAnalyzer().analyze(ticker)
        m = report["advanced_market"]

        print("Market structure       :", m.market_structure)
        print("Market score           :", m.score)
        print("Confidence             :", m.confidence)
        print("Coverage               :", m.coverage)
        print("Breadth regime         :", m.breadth_regime)
        print("Stock relative strength:", m.stock_relative_strength)
        print("Sector                 :", m.sector)
        print("Sector ETF             :", m.sector_etf)
        print("Sector regime          :", m.sector_regime)
        print("Participation          :", m.participation_regime)
        print("Realized volatility    :", m.volatility_state)
        print("Positives              :", m.positives)
        print("Risks                  :", m.risks)
        print("Unknowns               :", m.unknowns)

        print("\nSIGNALS")
        for name, sig in m.signals.items():
            if name in {
                "breadth", "equal_weight_vs_spy_20d",
                "stock_relative_strength", "sector_trend",
                "stock_vs_sector_20d", "relative_volume_20d",
                "realized_volatility_20d",
            }:
                print(
                    f"  {name:28} value={sig.get('value')} "
                    f"state={sig.get('state')} "
                    f"conf={sig.get('confidence')} "
                    f"as_of={sig.get('as_of')} "
                    f"source={sig.get('source')}"
                )

        print("\nMacro regime           :", report["macro_regime"].regime)
        print("Stock score            :", report["score"].overall_score)
        print("RESULT: PASS")

    except Exception as error:
        print("RESULT: FAILED", type(error).__name__, error)
