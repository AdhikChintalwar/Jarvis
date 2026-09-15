import sys,types
yf=types.ModuleType("yfinance");yf.Ticker=lambda *a,**k:None;yf.download=lambda *a,**k:None
sys.modules.setdefault("yfinance",yf)
from types import SimpleNamespace
from inspect import signature
from investor.valuation_engine import ValuationEngine
from investor.scoring_engine import StockScoringEngine

def vm(v,c=.85):
 return {"value":v,"status":"PRIMARY_ONLY","confidence":c,"source":"SEC_XBRL","period":"2025-12-31"}

primary={"verified_financials":{
 "revenue":vm(1000.),"net_income":vm(100.),"free_cash_flow":vm(80.),
 "cash":vm(200.),"debt":vm(50.),"revenue_growth_yoy":vm(.20)
}}
market=SimpleNamespace(current_price=10.)
fund=SimpleNamespace(market_cap=1500.,shares_outstanding=150.,forward_pe=13.)
r=ValuationEngine().analyze(market,fund,primary)
assert r.trailing_pe==15.
assert r.price_to_sales==1.5
assert r.enterprise_value==1350.
assert r.price_to_fcf==18.75
assert round(r.fcf_yield,2)==.05
assert r.growth_adjusted_pe==.75
assert r.coverage==100.
assert "valuation" in signature(StockScoringEngine.score).parameters

# Loss-making firms must not get a nonsensical negative P/E.
loss=dict(primary); loss={"verified_financials":dict(primary["verified_financials"])}
loss["verified_financials"]["net_income"]=vm(-20.)
lr=ValuationEngine().analyze(market,fund,loss)
assert lr.trailing_pe is None and lr.earnings_yield is not None and lr.earnings_yield<0

# Missing verified facts stay unknown rather than reviving Yahoo statement values.
missing=ValuationEngine().analyze(market,fund,{"verified_financials":{}})
assert missing.score==50.
assert missing.trailing_pe is None
assert missing.price_to_sales is None

print("V3.8 valuation contract: PASS")
print("score:",r.score,"confidence:",r.confidence,"coverage:",r.coverage)
print("PE:",r.trailing_pe,"P/S:",r.price_to_sales,"EV/S:",r.ev_to_sales,"FCF yield:",r.fcf_yield)
