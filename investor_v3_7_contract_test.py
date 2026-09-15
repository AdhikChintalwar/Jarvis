import sys, types
yf=types.ModuleType("yfinance")
yf.Ticker=lambda *a,**k: None
yf.download=lambda *a,**k: None
sys.modules.setdefault("yfinance",yf)
from inspect import signature
from investor.accounting_quality import AccountingQualityEngine
from investor.scoring_engine import StockScoringEngine
def vm(v):return {"value":v,"status":"PRIMARY_ONLY","confidence":.85,"source":"SEC_XBRL","period":"2025-12-31"}
p={"verified_financials":{"revenue":vm(1000.),"net_income":vm(100.),"operating_cash_flow":vm(140.),"free_cash_flow":vm(110.),"cash":vm(300.),"debt":vm(100.),"shares_change_yoy":vm(-.05)},
"annual_history":{"periods":[{"operating_margin":.12,"net_margin":.08,"free_cash_flow_margin":.08,"weighted_average_diluted_shares":100.},{"operating_margin":.16,"net_margin":.10,"free_cash_flow_margin":.11,"weighted_average_diluted_shares":96.}]}}
r=AccountingQualityEngine().analyze(p)
assert r.score>50 and r.coverage>=75 and r.cash_conversion==1.4 and r.net_cash==200. and r.operating_margin_change_pp==4.
assert "accounting_quality" in signature(StockScoringEngine.score).parameters
m=AccountingQualityEngine().analyze({"verified_financials":{},"annual_history":{"periods":[]}})
assert m.score==50. and m.coverage==0. and not m.red_flags
print("V3.7 accounting-quality contract: PASS")
print("score:",r.score,"confidence:",r.confidence,"coverage:",r.coverage)
