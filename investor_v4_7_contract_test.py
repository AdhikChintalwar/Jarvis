from dataclasses import asdict
import pandas as pd, numpy as np
from investor.decision_engine import DecisionEngine
from investor.validation_engine import ValidationEngine
from investor.trade_plan_v46 import TradePlanAgent

# Decision authority is deterministic.
report={
"financial_health":{"quality_score":80,"evidence_confidence":90,"evidence_coverage":100},
"accounting_quality":{"score":75,"confidence":85,"coverage":100},
"valuation":{"score":65,"confidence":80,"coverage":100},
"event_intelligence":{"score":55,"confidence":70,"coverage":100},
"macro_regime":{"score":50,"confidence":80,"coverage":100},
"advanced_market":{"score":70,"confidence":75,"coverage":100},
"unified_risk":{"risk_score":30,"confidence":85,"coverage":100,"risk_level":"LOW","hard_overrides":[],"position_risk_multiplier":1},
}
d=DecisionEngine().evaluate(report)
assert d.score>0 and d.research_state in {"WATCH","CANDIDATE","TOP_RESEARCH","WAIT","AVOID"}

# Missing module is omitted, not scored bearish.
r2=dict(report);r2["valuation"]={}
d2=DecisionEngine().evaluate(r2)
assert "valuation" in d2.unknowns and d2.evidence_coverage<100

# Risk sovereignty.
r3=dict(report);r3["unified_risk"]={"risk_score":90,"confidence":90,"coverage":100,"risk_level":"VERY_HIGH","hard_overrides":["extreme_volatility"],"position_risk_multiplier":.4}
d3=DecisionEngine().evaluate(r3)
assert d3.research_state in {"AVOID","WAIT","WATCH"}

# Authority preservation: upstream REVIEW cannot become PASS.
vreport={"primary_financial":{"verified_financials":{
"revenue":{"value":100,"status":"STRONG_AGREEMENT","confidence":.97},
"net_income":{"value":10,"status":"STRONG_AGREEMENT","confidence":.97},
"free_cash_flow":{"value":9,"status":"REVIEW","confidence":.72},
"operating_cash_flow":{"value":12,"status":"STRONG_AGREEMENT","confidence":.97},
"cash":{"value":20,"status":"PERIOD_MISMATCH","confidence":.7},
"debt":{"value":5,"status":"STRONG_AGREEMENT","confidence":.97}}},
"technical":{"sma_20":110,"sma_50":105,"ema_20":109}}
dates=pd.date_range("2026-01-01",periods=80,freq="B")
close=pd.Series(np.linspace(100,120,80),index=dates)
hist=pd.DataFrame({"Open":close-.2,"High":close+1,"Low":close-1,"Close":close,"Volume":1_000_000})
# use independently recalculated metrics to avoid false mismatch in synthetic test
vreport["technical"]["sma_20"]=float(close.tail(20).mean());vreport["technical"]["sma_50"]=float(close.tail(50).mean());vreport["technical"]["ema_20"]=float(close.ewm(span=20,adjust=False).mean().iloc[-1])
vr=ValidationEngine().validate(vreport,hist)
m={x["name"]:x["status"] for x in vr.checks}
assert m["primary.free_cash_flow"]=="REVIEW"
assert m["primary.cash"]=="REVIEW"
assert m["technical.sma_20"]=="PASS" and m["technical.sma_50"]=="PASS"

# External disagreement must surface, not overwrite primary.
vr2=ValidationEngine().validate(vreport,hist,{"source":"independent_test","revenue":200})
assert any(x["name"]=="external.revenue" and x["status"]=="FAIL" for x in vr2.checks)

print("V4.7 stabilization contract: PASS")
print("decision:",d.score,d.research_state)
print("missing-module coverage:",d2.evidence_coverage)
print("hard-risk state:",d3.research_state)
print("validation authority:",m["primary.free_cash_flow"],m["primary.cash"])
