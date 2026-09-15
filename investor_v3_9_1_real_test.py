from investor.analyzer import StockAnalyzer
for ticker in ("AAPL","SLDE","CRWD"):
 print("\n"+"="*98+"\nV3.9.1 REAL ANALYSIS:",ticker,"\n"+"="*98)
 try:
  r=StockAnalyzer().analyze(ticker);e=r["event_intelligence"]
  print("Event score       :",e.score)
  print("Confidence        :",e.confidence)
  print("Coverage          :",e.coverage)
  print("Positive pressure :",e.positive_pressure)
  print("Negative pressure :",e.negative_pressure)
  print("Active / primary  :",e.active_event_count,e.primary_event_count)
  print("Unknowns          :",e.unknowns)
  print("SEC contextual events:")
  for x in [x for x in e.events if x.event_type.startswith("sec_")][:20]:
   print(" ",x.event_date,x.event_type,x.direction,"form=",x.filing_form,
         "effective_conf=",x.effective_confidence,"|",x.title)
   for n in x.notes[:3]: print("    -",n)
  print("Deep SEC raw dilution:",r["deep_sec"].dilution_risk,r["deep_sec"].dilution_score)
  print("RESULT: PASS")
 except Exception as ex:
  print("RESULT: FAILED",type(ex).__name__,ex)
