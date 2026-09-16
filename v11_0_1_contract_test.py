from baby_ui_backend.v11 import V11InvestmentPlatform
import tempfile, os

def m(k,v,status='PASS'): return {'key':k,'value':v,'status':status,'inputs':{}}
def s(i,ms,cov=100,status='PASS',score=None):
 d={'id':i,'metrics':ms,'coverage':cov,'status':status}
 if score is not None:d['score']=score
 return d

def flow(sym='TEST'):
 return {'symbol':sym,'trade_plan':{'status':'WAIT_FOR_PULLBACK_OR_BREAKOUT'},'current_setup':{'status':'WAIT_FOR_PULLBACK_OR_BREAKOUT'},'paper_proposal':{'eligible':False,'status':'WAITING'},'portfolio':{}}

company={'stages':[
 s('fundamentals_v101',[m('revenue_growth_yoy',25),m('net_income_growth_yoy',15),m('ocf_growth_yoy',12),m('fcf_growth_yoy',18),m('net_margin',20),m('fcf',1000),m('cash',500),m('debt',200)],100,score=70),
 s('technical_v102',[m('trend_regime','BULLISH'),m('rsi14',60),m('rvol',1.2)],100,score=65),
 s('events_v103',[],50,score=50),s('macro_v104',[],50,score=50),
 s('valuation_v105',[m('pe_ttm',45),m('fcf_yield_ttm',3.5),m('reverse_dcf_growth',40)],100,score=55),
 s('institutional_v106',[m('put_call',None,'UNKNOWN')],0,status='UNKNOWN') ]}
research={'symbol':'TEST','decision':'WATCH','score':55,'confidence':75,'coverage':100,'risk':'MODERATE','hard_risk_override':False}
with tempfile.TemporaryDirectory() as td:
 p=V11InvestmentPlatform(os.path.join(td,'j.db')); o=p.build('TEST',research,company,flow())
 assert o['schema_version']=='11.0.1'
 assert o['expectations']['observed_revenue_growth']==25
 assert o['expectations']['status']=='BALANCED' and o['expectations']['expectation_gap_pct_points']==15
 assert all(k in o['decision'] for k in ('pipeline_coverage','evidence_coverage','decision_grade_coverage'))
 assert o['thesis']['bull_weight']>0 and o['thesis']['bear_weight']>0
 assert o['decision']['ai_scoring_authority']=='0%'
 # ETF: fundamentals/valuation not applicable and thesis must be market-led.
 etf={'stages':[s('fundamentals_v101',[],0,'NOT_APPLICABLE'),s('technical_v102',[m('trend_regime','BULLISH'),m('rsi14',55),m('rvol',1.1)],100,score=60),s('events_v103',[],100,score=50),s('macro_v104',[],50,score=50),s('valuation_v105',[],0,'NOT_APPLICABLE'),s('institutional_v106',[],0,'UNKNOWN')]}
 oe=p.build('SPY',dict(research,symbol='SPY',confidence=40),etf,flow('SPY'))
 assert oe['thesis']['asset_type']=='ETF'
 assert any(x['kind']=='MARKET' for x in oe['thesis']['bull_case'])
 assert oe['expectations']['status']=='NOT_APPLICABLE'
 assert oe['decision']['decision_grade_coverage']<100
 # Severe risk must outweigh weak positives and preserve cap.
 rr=dict(research,hard_risk_override=True,risk='VERY_HIGH')
 orisk=p.build('TEST',rr,company,flow())
 assert orisk['decision']['score']<=44 and orisk['decision']['state'] in {'WAIT','AVOID'}
print('BABY V11.0.1 DECISION INTELLIGENCE HARDENING: PASS')
print('Aligned expectations growth keys: PASS')
print('Pipeline/evidence/decision-grade coverage split: PASS')
print('Weighted evidence materiality: PASS')
print('ETF market-led thesis: PASS')
print('Hard-risk cap: PASS')
print('AI scoring authority: 0%')
print('Real money: DISABLED')
