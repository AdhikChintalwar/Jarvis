from investor.analyzer import StockAnalyzer
for ticker in ("AAPL","SLDE","CRWD"):
 print("\n"+"="*96+"\nV3.9 REAL ANALYSIS:",ticker,"\n"+"="*96)
 try:
  r=StockAnalyzer().analyze(ticker);e=r["event_intelligence"]
  print("Event score          :",e.score)
  print("Confidence           :",e.confidence)
  print("Coverage             :",e.coverage)
  print("Positive pressure    :",e.positive_pressure)
  print("Negative pressure    :",e.negative_pressure)
  print("Active events        :",e.active_event_count)
  print("Primary events       :",e.primary_event_count)
  print("Secondary events     :",e.secondary_event_count)
  print("High materiality     :",e.high_materiality_count)
  print("Positives            :",e.positives)
  print("Risks                :",e.risks)
  print("Unknowns             :",e.unknowns)
  print("Top events:")
  for x in e.events[:12]:
   print(" ",x.event_date,x.evidence_class,x.event_type,x.direction,x.materiality,
         "age=",x.age_days,"fresh=",x.freshness,"conf=",x.effective_confidence,
         "form=",x.filing_form,"|",x.title[:100])
  print("Deep SEC dilution    :",r["deep_sec"].dilution_risk,r["deep_sec"].dilution_score)
  print("Deep SEC distress    :",r["deep_sec"].distress_risk,r["deep_sec"].distress_score)
  print("RESULT: PASS")
 except Exception as ex:
  print("RESULT: FAILED",type(ex).__name__,ex)
