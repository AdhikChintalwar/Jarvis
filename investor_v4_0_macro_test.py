import sys,types,os
import pandas as pd
import numpy as np

class FakeTicker:
 def __init__(self,s): self.s=s
 def history(self,**kwargs):
  n=30
  base={"SPY":500,"QQQ":450,"IWM":220,"^VIX":15,"^TNX":4.0}[self.s]
  if self.s in ("SPY","QQQ","IWM"): arr=np.linspace(base*.94,base,n)
  elif self.s=="^VIX": arr=np.linspace(17,15,n)
  else: arr=np.linspace(4.3,4.0,n)
  return pd.DataFrame({"Close":arr},index=pd.date_range("2026-08-01",periods=n))
yf=types.ModuleType("yfinance");yf.Ticker=FakeTicker
sys.modules["yfinance"]=yf
os.environ.pop("FRED_API_KEY",None)
from investor.macro_regime import MacroRegimeEngine
r=MacroRegimeEngine().analyze()
assert r.regime=="RISK_ON",r
assert r.equity_regime=="bullish"
assert r.volatility_regime=="calm"
assert r.rate_regime=="falling"
assert "fred_cpi" in r.unknowns
assert r.coverage==62.5
assert r.confidence==70.0
print("V4.0 macro-regime contract: PASS")
print("regime:",r.regime,"score:",r.score,"confidence:",r.confidence,"coverage:",r.coverage)
print("equity:",r.equity_regime,"vix:",r.volatility_regime,"rates:",r.rate_regime)
print("unknowns:",r.unknowns)
