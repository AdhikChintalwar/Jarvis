from investor.analyzer import StockAnalyzer

for ticker in ("AAPL", "SLDE", "CRWD"):
    print("\n" + "=" * 100)
    print("V4.0.1 REAL ANALYSIS:", ticker)
    print("=" * 100)

    try:
        report = StockAnalyzer().analyze(ticker)
        m = report["macro_regime"]

        print("Macro regime          :", m.regime)
        print("Macro score           :", m.score)
        print("Confidence            :", m.confidence)
        print("Coverage              :", m.coverage)
        print("Cache age seconds     :", m.cache_age_seconds)

        print("\nPOLICY / INFLATION / LABOR")
        print("Fed funds             :", m.fed_funds_rate)
        print("Fed policy state      :", m.fed_policy_state)
        print("CPI YoY %             :", m.cpi_yoy_pct)
        print("CPI MoM %             :", m.cpi_mom_pct)
        print("Inflation regime      :", m.inflation_regime)
        print("Unemployment %        :", m.unemployment_rate)
        print("Unemployment 3m pp    :", m.unemployment_change_3m_pp)
        print("Labor regime          :", m.labor_regime)

        print("\nRATES / CURVE")
        print("2Y Treasury           :", m.treasury_2y)
        print("10Y Treasury          :", m.treasury_10y)
        print("2s10s spread bp       :", m.yield_curve_2s10s_bp)
        print("Yield curve           :", m.yield_curve_state)
        print("Rate regime           :", m.rate_regime)

        print("\nMARKET")
        print("Equity regime         :", m.equity_regime)
        print("Volatility regime     :", m.volatility_regime)
        print("Financial conditions  :", m.financial_conditions)

        print("\nPOSITIVES              :", m.positives)
        print("RISKS                  :", m.risks)
        print("UNKNOWNS               :", m.unknowns)

        for key, value in m.observations.items():
            print(
                f"  {key:14} value={value.get('value')} "
                f"trend={value.get('trend')} "
                f"as_of={value.get('as_of')} "
                f"source={value.get('source')} "
                f"auth={value.get('authority')}"
            )

        print("\nStock score           :", report["score"].overall_score)
        print("RESULT: PASS")

    except Exception as error:
        print("RESULT: FAILED", type(error).__name__, error)
