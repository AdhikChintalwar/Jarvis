from types import SimpleNamespace as NS
import sys, types
if "yfinance" not in sys.modules:
    y=types.ModuleType("yfinance")
    y.download=lambda *a,**k: None
    y.Ticker=type("Ticker",(),{"__init__":lambda self,*a,**k:None})
    sys.modules["yfinance"]=y
import pandas as pd, numpy as np
from investor.decision_engine import DecisionEngine
from investor.validation_engine import ValidationEngine
from investor.investment_system import BabyInvestmentSystem

n=260
close=pd.Series(np.linspace(80,120,n)+np.sin(np.arange(n)/8),name='Close')
h=pd.DataFrame({'Close':close,'Open':close-.2,'High':close+1,'Low':close-1,'Volume':1_000_000})
# Technical values independently matching ValidationEngine conventions.
sma20=float(close.tail(20).mean()); sma50=float(close.tail(50).mean()); ema20=float(close.ewm(span=20,adjust=False).mean().iloc[-1])
d=close.diff();g=d.clip(lower=0);l=-d.clip(upper=0);ag=g.ewm(alpha=1/14,adjust=False,min_periods=14).mean();al=l.ewm(alpha=1/14,adjust=False,min_periods=14).mean();loss=float(al.iloc[-1]);gain=float(ag.iloc[-1]);rsi=100.0 if loss==0 and gain>0 else (50.0 if loss==0 else 100-(100/(1+gain/loss)))
tech=NS(sma_20=sma20,sma_50=sma50,sma_200=100,ema_9=118,ema_20=ema20,ema_50=112,ema_200=100,rsi_14=rsi,atr_14=2.0,distance_from_ema20_pct=2.0)
risk=NS(annualized_volatility=30)
pf={'verified_financials':{k:{'value':v,'status':'PRIMARY_ONLY','confidence':.9} for k,v in {'revenue':1000,'net_income':100,'free_cash_flow':120,'operating_cash_flow':140,'cash':500,'debt':100}.items()}}
report={'ticker':'TEST','market':NS(current_price=float(close.iloc[-1])), 'technical':tech,'risk':risk,'primary_financial':pf,
'financial_health':NS(score=72,evidence_confidence=90,evidence_coverage=100),
'accounting_quality':NS(score=70,confidence=80,coverage=100),'valuation':NS(score=65,confidence=75,coverage=100),
'event_intelligence':NS(score=55,confidence=80,coverage=80),'macro_regime':NS(score=45,confidence=90,coverage=100),
'advanced_market':NS(score=68,confidence=70,coverage=100),
'unified_risk':NS(risk_score=35,risk_level='LOW',confidence=85,coverage=100,hard_overrides=[],position_risk_multiplier=1.0)}

d=DecisionEngine().evaluate(report)
assert round(d.score,2)==64.85, d
assert d.research_state=='CANDIDATE'
v=ValidationEngine().validate(report,h,{'source':'independent_fixture','revenue':1000,'net_income':100,'current_price':float(close.iloc[-1])})
assert v.checks_failed==0
x=BabyInvestmentSystem().evaluate(report,h,{'source':'independent_fixture','revenue':1000},100000)
assert x.ai_scoring_authority==0.0
assert x.execution_authority=='NONE'
assert x.trade_plan is not None
print('V4.6 deterministic-decision contract: PASS')
print('decision score:',d.score,'state:',d.research_state)
print('validation:',v.status,v.score)
print('AI scoring authority:',x.ai_scoring_authority)
print('execution authority:',x.execution_authority)
