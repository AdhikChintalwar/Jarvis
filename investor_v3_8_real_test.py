from investor.analyzer import StockAnalyzer
for ticker in ("AAPL","SLDE","CRWD"):
 print("\n"+"="*92+"\nV3.8 REAL ANALYSIS:",ticker,"\n"+"="*92)
 try:
  r=StockAnalyzer().analyze(ticker);v=r["valuation"];s=r["score"]
  print("Valuation score       :",v.score)
  print("Confidence            :",v.confidence)
  print("Coverage              :",v.coverage)
  print("Market cap            :",v.market_cap)
  print("Enterprise value      :",v.enterprise_value)
  print("Trailing P/E          :",v.trailing_pe)
  print("Forward P/E secondary :",v.forward_pe)
  print("Price / Sales         :",v.price_to_sales)
  print("EV / Sales            :",v.ev_to_sales)
  print("Price / FCF           :",v.price_to_fcf)
  print("EV / FCF              :",v.ev_to_fcf)
  print("Earnings yield        :",v.earnings_yield)
  print("FCF yield             :",v.fcf_yield)
  print("Growth-adjusted P/E   :",v.growth_adjusted_pe)
  print("Positive              :",v.positive_signals)
  print("Red flags             :",v.red_flags)
  print("Unknowns              :",v.unknowns)
  print("Overall stock score   :",s.overall_score)
  print("Overall confidence    :",s.confidence)
  print("Valuation component   :",[c.score for c in s.components if c.name=="valuation"])
  print("RESULT: PASS")
 except Exception as e:
  print("RESULT: FAILED",type(e).__name__,e)
