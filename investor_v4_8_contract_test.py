from types import SimpleNamespace as NS
import pandas as pd
import numpy as np
from investor.investment_system import BabyInvestmentSystem
from investor.providers.alpha_vantage_provider import AlphaVantageProvider
from investor.validation_engine import ValidationEngine

class FakeProvider:
    def build_reference(self,symbol):
        return {"symbol":symbol,"source":"Alpha Vantage fixture","provider":"ALPHA_VANTAGE",
                "independent":True,"status":"ACTIVE","market_as_of":"2026-09-15",
                "financial_as_of":"2025-12-31","as_of":"2026-09-15",
                "current_price":100.0,"sma_20":95.5,"sma_50":91.0,"ema_20":95.0,"rsi_14":55.0,
                "revenue":1000.0,"net_income":100.0,"operating_cash_flow":150.0,
                "free_cash_flow":120.0,"cash":200.0,"debt":50.0,"warnings":[]}

idx=pd.date_range("2026-01-01",periods=80,freq="B")
close=pd.Series(np.linspace(80,100,80),index=idx)
h=pd.DataFrame({"Open":close-.5,"High":close+1,"Low":close-1,"Close":close,"Volume":1_000_000})
# Analyzer technical values are intentionally fixture values matching independent packet where tested.
tech=NS(sma_20=95.5,sma_50=91.0,ema_20=95.0,rsi_14=55.0)
risk=NS(risk_level="LOW",hard_override=False,risk_score=20)
def m(v,status="PASS"): return NS(value=v,status=status,confidence=.97)
pf=NS(verified_financials=NS(revenue=m(1000),net_income=m(100),free_cash_flow=m(120),
    operating_cash_flow=m(150),cash=m(200),debt=m(50)))
report={"ticker":"TEST","market":NS(current_price=100.0),"technical":tech,"risk":risk,
        "primary_financial":pf,"financial_health":NS(score=70,confidence=80,coverage=100),
        "accounting_quality":NS(score=70,confidence=80,coverage=100),
        "valuation":NS(score=60,confidence=80,coverage=100,context="FAIR"),
        "unified_risk":NS(risk_level="LOW",risk_score=20,hard_override=False,confidence=80,coverage=100)}

r=BabyInvestmentSystem(external_provider=FakeProvider()).evaluate(report,h)
assert r.external_provider["independent"] is True
assert r.external_provider["status"]=="ACTIVE"
ext=[x for x in r.validation["checks"] if x["name"].startswith("external.")]
assert ext and any(x["name"]=="external.revenue" and x["status"]=="PASS" for x in ext)
assert any(x["name"]=="external.current_price" and x["status"]=="PASS" for x in ext)
assert r.ai_scoring_authority==0.0 and r.execution_authority=="NONE"

# Same-source/unverified packet must be rejected.
v=ValidationEngine().validate(report,h,{"source":"Yahoo","revenue":1000})
x=[c for c in v.checks if c["name"]=="external_cross_source"][0]
assert x["status"]=="UNKNOWN"

# External disagreement must surface, never overwrite primary.
v2=ValidationEngine().validate(report,h,{"source":"Alpha Vantage fixture","provider":"ALPHA_VANTAGE",
    "independent":True,"status":"ACTIVE","revenue":700.0})
x=[c for c in v2.checks if c["name"]=="external.revenue"][0]
assert x["status"]=="FAIL"
assert report["primary_financial"].verified_financials.revenue.value==1000

print("V4.8 independent-provider contract: PASS")
print("provider:",r.external_provider)
print("validation:",r.validation["status"],r.validation["score"],"coverage",r.validation["coverage"])
print("AI scoring authority:",r.ai_scoring_authority,"execution:",r.execution_authority)
