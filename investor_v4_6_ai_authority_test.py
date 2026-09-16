import sys,types
if 'yfinance' not in sys.modules:
 y=types.ModuleType('yfinance');y.download=lambda *a,**k:None;y.Ticker=type('T',(),{'__init__':lambda s,*a,**k:None});sys.modules['yfinance']=y
if 'openai' not in sys.modules:
 o=types.ModuleType('openai');o.OpenAI=object;sys.modules['openai']=o
from types import SimpleNamespace as NS
from investor.committee.committee_guard import FinalCommitteeGuard
G=FinalCommitteeGuard()
e={'financial_health':NS(score=70,evidence_confidence=90,evidence_coverage=100),'accounting_quality':NS(score=70,confidence=90,coverage=100),'valuation':NS(score=70,confidence=90,coverage=100),'event_intelligence':NS(score=70,confidence=90,coverage=100),'macro_regime':NS(score=70,confidence=90,coverage=100),'advanced_market':NS(score=70,confidence=90,coverage=100),'unified_risk':NS(risk_score=30,risk_level='LOW',confidence=90,coverage=100,hard_overrides=[])}
g=G.evaluate(e)
a=G.apply(99,'TOP_CANDIDATE',99,100,g);b=G.apply(1,'AVOID',1,100,g)
assert a['final_score']==b['final_score']==g.deterministic_score
assert a['decision']==b['decision']
assert a['llm_weight']==b['llm_weight']==0
assert a['llm_score'] is None and b['llm_score'] is None
print('V4.6 AI-authority isolation contract: PASS')
print('deterministic score:',a['final_score'],'decision:',a['decision'])
print('Nemotron score authority:',a['ai_scoring_authority'])
print('Nemotron decision authority:',a['ai_decision_authority'])
