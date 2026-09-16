import yfinance as yf
from datetime import datetime,timezone,timedelta
from investor.v65 import BabyHistoricalValidationPlatform

CASES=[("AAPL","320193","2025-02-15"),("CRWD","1535527","2025-06-15")]
def history(symbol,end):
    e=datetime.fromisoformat(end)+timedelta(days=1)
    s=e-timedelta(days=500)
    return yf.download(symbol,start=s.date().isoformat(),end=e.date().isoformat(),
                       auto_adjust=True,actions=False,progress=False,threads=False)

p=BabyHistoricalValidationPlatform()
for symbol,cik,date in CASES:
    h=history(symbol,date)
    spy=history("SPY",date)
    if hasattr(h.columns,"levels"):
        h=h.xs(symbol,axis=1,level=1) if symbol in h.columns.get_level_values(1) else h.droplevel(1,axis=1)
    if hasattr(spy.columns,"levels"):
        spy=spy.xs("SPY",axis=1,level=1) if "SPY" in spy.columns.get_level_values(1) else spy.droplevel(1,axis=1)
    r=p.research(symbol,cik,date+"T23:59:59+00:00",h,spy)
    d=r["decision"]
    print("\n",symbol,date)
    print("evidence:",sorted(r["snapshot"].evidence))
    print("macro source:",r["macro"]["source"],"coverage:",r["macro"]["coverage"])
    print("decision:",d["research_state"],"score:",d["score"],"confidence:",d["evidence_confidence"],"coverage:",d["evidence_coverage"])
    print("risk:",d["report"]["unified_risk"]["risk_level"],d["report"]["unified_risk"]["risk_score"])
    assert d["ai_scoring_authority"]==0 and d["ai_execution_authority"]==0
    assert r["market"].as_of<=date
print("\nV6.5 REAL HISTORICAL REPLAY: PASS")
print("NOTE: market OHLCV source in this gate is Yahoo/yfinance secondary/prototype; SEC and ALFRED remain primary PIT evidence.")
