from types import SimpleNamespace as NS
import numpy as np
import pandas as pd

from investor.trade_plan_v46 import TradePlanAgent
from investor.validation_engine import ValidationEngine

# Full compatibility adapter must not crash when legacy technical fields are absent.
idx=pd.date_range("2025-01-01",periods=260,freq="B")
close=pd.Series(np.linspace(80,120,260),index=idx)
h=pd.DataFrame({"Open":close-.5,"High":close+1,"Low":close-1,"Close":close,"Volume":1_000_000})
minimal=NS(sma_20=118.0,sma_50=116.0,ema_20=118.5,rsi_14=60.0)
adapter=TradePlanAgent._legacy_technical_adapter(minimal,h,2.0)
for field in ("atr_14","sma_20","sma_50","sma_200","ema_20","ema_50","ema_200","rsi_14"):
    assert hasattr(adapter,field), field
assert adapter.ema_50 is not None
assert adapter.sma_200 is not None

# Balance-sheet concept disagreement must surface as REVIEW, never silently PASS
# and never automatically condemn SEC primary evidence as FAIL.
report={"primary_financial":{"verified_financials":{
    "revenue":{"value":1000.0,"status":"PASS","confidence":.97},
    "net_income":{"value":100.0,"status":"PASS","confidence":.97},
    "operating_cash_flow":{"value":150.0,"status":"PASS","confidence":.97},
    "free_cash_flow":{"value":120.0,"status":"PASS","confidence":.97},
    "cash":{"value":100.0,"status":"REVIEW","confidence":.70},
    "debt":{"value":100.0,"status":"REVIEW","confidence":.70},
}}}
ext={"source":"Alpha Vantage fixture","provider":"ALPHA_VANTAGE","independent":True,
     "status":"ACTIVE","financial_as_of":"2025-12-31",
     "revenue":1000.0,"net_income":100.0,"operating_cash_flow":150.0,
     "free_cash_flow":120.0,"cash":70.0,"debt":160.0}
v=ValidationEngine().validate(report,None,ext)
checks={x["name"]:x for x in v.checks}
assert checks["external.revenue"]["status"]=="PASS"
assert checks["external.cash"]["status"]=="REVIEW"
assert checks["external.debt"]["status"]=="REVIEW"
assert "CONCEPT_MISMATCH_MATERIAL" in checks["external.cash"]["note"]
assert "CONCEPT_MISMATCH_MATERIAL" in checks["external.debt"]["note"]

# A true flow-metric disagreement remains strict.
ext_bad=dict(ext); ext_bad["revenue"]=700.0
v2=ValidationEngine().validate(report,None,ext_bad)
c={x["name"]:x for x in v2.checks}
assert c["external.revenue"]["status"]=="FAIL"

print("V4.8.2 stabilization contract: PASS")
print("legacy technical adapter: PASS")
print("balance concept authority preservation: PASS")
print("flow metric strict disagreement: PASS")
