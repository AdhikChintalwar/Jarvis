import re
from types import SimpleNamespace as NS
import numpy as np
import pandas as pd

from investor.trade_plan_v46 import TradePlanAgent
import investor.trade_plan as legacy_module

source=open(legacy_module.__file__,"r",encoding="utf-8").read()
technical_required=sorted(set(re.findall(r"\btechnical\.([A-Za-z_][A-Za-z0-9_]*)",source)))
risk_required=sorted(set(re.findall(r"\brisk\.([A-Za-z_][A-Za-z0-9_]*)",source)))

idx=pd.date_range("2025-01-01",periods=260,freq="B")
close=pd.Series(np.linspace(80,120,260),index=idx)
history=pd.DataFrame({
    "Open":close-.5,"High":close+1,"Low":close-1,
    "Close":close,"Volume":1_000_000
})

technical=TradePlanAgent._legacy_technical_adapter(NS(ema_20=118.0),history,2.0)
risk=TradePlanAgent._legacy_risk_adapter(NS())

missing_t=[x for x in technical_required if not hasattr(technical,x) or getattr(technical,x) is None]
missing_r=[x for x in risk_required if not hasattr(risk,x) or getattr(risk,x) is None]
assert not missing_t, f"technical compatibility missing: {missing_t}"
assert not missing_r, f"risk compatibility missing: {missing_r}"

# Sovereignty invariant: adapters cannot create or suppress the actual unified-risk gate.
assert not hasattr(risk,"hard_overrides")
assert not hasattr(risk,"risk_level")

print("V4.8.4 complete compatibility-boundary contract: PASS")
print("technical dependencies:",technical_required)
print("risk dependencies:",risk_required)
print("risk annualized_volatility:",risk.annualized_volatility)
