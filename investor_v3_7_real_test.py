from investor.analyzer import StockAnalyzer
for ticker in ("AAPL","SLDE","CRWD"):
 print("\n"+"="*90+"\nV3.7 REAL ANALYSIS:",ticker,"\n"+"="*90)
 try:
  r=StockAnalyzer().analyze(ticker);a=r["accounting_quality"];s=r["score"]
  print("Accounting score:",a.score);print("Confidence:",a.confidence);print("Coverage:",a.coverage);print("History periods:",a.history_periods);print("History confidence:",a.history_confidence)
  print("Cash conversion:",a.cash_conversion);print("FCF margin:",a.fcf_margin);print("Cash earnings gap:",a.cash_earnings_gap_ratio)
  print("Net cash:",a.net_cash);print("Cash/debt:",a.cash_to_debt);print("Shares YoY:",a.shares_change_yoy)
  print("Operating margin Δ pp:",a.operating_margin_change_pp);print("Net margin Δ pp:",a.net_margin_change_pp);print("FCF margin Δ pp:",a.fcf_margin_change_pp)
  print("Positive:",a.positive_signals);print("Red flags:",a.red_flags);print("Unknowns:",a.unknowns)
  print("History periods:",len((r["primary_financial"] or {}).get("annual_history",{}).get("periods",[])))
  print("Overall:",s.overall_score,"Confidence:",s.confidence)
  print("Accounting component:",[c.score for c in s.components if c.name=="accounting_quality"])
  print("RESULT: PASS")
 except Exception as e: print("RESULT: FAILED",type(e).__name__,e)
