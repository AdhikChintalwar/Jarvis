import sys,types
yf=types.ModuleType("yfinance");yf.Ticker=lambda *a,**k:None;yf.download=lambda *a,**k:None
sys.modules.setdefault("yfinance",yf)
from types import SimpleNamespace
from investor.valuation_engine import ValuationEngine

def vm(v,period="2025-12-31"):
 return {"value":v,"status":"PRIMARY_ONLY","confidence":.85,"source":"SEC_XBRL","period":period}

market=SimpleNamespace(current_price=10.,as_of_date="2026-09-15")
fund=SimpleNamespace(market_cap=1500.,shares_outstanding=150.,forward_pe=13.)

base={"verified_financials":{
 "revenue":vm(1000.),"net_income":vm(100.),"free_cash_flow":vm(80.),
 "cash":vm(200.),"debt":vm(50.),"revenue_growth_yoy":vm(.20)
}}
r=ValuationEngine().analyze(market,fund,base)
assert r.profitability_state=="PROFITABLE"
assert r.fcf_state=="FCF_POSITIVE"
assert r.trailing_pe==15.
assert r.earnings_yield>0
assert r.market_data_as_of=="2026-09-15"
assert r.financial_period=="2025-12-31"
assert r.absolute_valuation_score is not None and r.growth_adjusted_score is not None

loss={"verified_financials":dict(base["verified_financials"])}
loss["verified_financials"]["net_income"]=vm(-20.)
lr=ValuationEngine().analyze(market,fund,loss)
assert lr.profitability_state=="LOSS_MAKING"
assert lr.trailing_pe is None
assert lr.earnings_yield is None
assert "trailing_pe" in lr.unknowns
assert any("loss-making" in x.lower() for x in lr.red_flags)

badfcf={"verified_financials":dict(base["verified_financials"])}
badfcf["verified_financials"]["free_cash_flow"]=vm(-10.)
fr=ValuationEngine().analyze(market,fund,badfcf)
assert fr.fcf_state=="FCF_NEGATIVE"
assert fr.price_to_fcf is None and fr.ev_to_fcf is None and fr.fcf_yield is None
assert any("free cash flow" in x.lower() for x in fr.red_flags)

missing=ValuationEngine().analyze(market,fund,{"verified_financials":{}})
assert missing.score==50.
assert missing.profitability_state=="UNKNOWN"
assert missing.fcf_state=="UNKNOWN"

print("V3.8.1 valuation semantics/calibration: PASS")
print("profitable:",r.score,r.absolute_valuation_score,r.growth_adjusted_score)
print("loss-making PE/yield:",lr.trailing_pe,lr.earnings_yield)
print("negative-FCF multiples:",fr.price_to_fcf,fr.ev_to_fcf,fr.fcf_yield)
