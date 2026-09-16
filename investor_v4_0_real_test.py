from investor.analyzer import StockAnalyzer
for ticker in ("AAPL","SLDE","CRWD"):
 print("\n"+"="*100+"\nV4.0 REAL ANALYSIS:",ticker,"\n"+"="*100)
 try:
  r=StockAnalyzer().analyze(ticker);m=r["macro_regime"]
  print("Macro regime         :",m.regime)
  print("Macro score          :",m.score)
  print("Confidence           :",m.confidence)
  print("Coverage             :",m.coverage)
  print("Financial conditions :",m.financial_conditions)
  print("Equity regime        :",m.equity_regime)
  print("Volatility regime    :",m.volatility_regime)
  print("Rate regime          :",m.rate_regime)
  print("Inflation regime     :",m.inflation_regime)
  print("Labor regime         :",m.labor_regime)
  print("Fed policy state     :",m.fed_policy_state)
  print("Positives            :",m.positives)
  print("Risks                :",m.risks)
  print("Unknowns             :",m.unknowns)
  for k,v in m.observations.items():
   print(f"  {k:12} value={v.get('value')} 20d={v.get('change_20d_pct')} trend={v.get('trend')} as_of={v.get('as_of')} source={v.get('source')} auth={v.get('authority')}")
  print("Stock score          :",r["score"].overall_score)
  print("RESULT: PASS")
 except Exception as ex:
  print("RESULT: FAILED",type(ex).__name__,ex)
