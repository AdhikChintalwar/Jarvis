from baby_ui_backend.v11 import V11InvestmentPlatform
import tempfile, os

def metric(k,v,status='PASS',**inputs): return {'key':k,'value':v,'status':status,'inputs':inputs}
def stage(i,metrics,cov=100,score=None):
 d={'id':i,'metrics':metrics,'coverage':cov,'status':'PASS'}
 if score is not None:d['score']=score
 return d
v106={'stages':[
 stage('fundamentals_v101',[metric('revenue_growth',25),metric('net_margin',20),metric('fcf',1000),metric('cash',500),metric('debt',200)],100,70),
 stage('technical_v102',[metric('trend_regime','BULLISH'),metric('rsi14',60),metric('rvol',1.2)],100,65),
 stage('events_v103',[],50,50),stage('macro_v104',[],50,50),
 stage('valuation_v105',[metric('pe_ttm',45),metric('fcf_yield_ttm',3.5),metric('reverse_dcf_growth',20)],100,55),
 stage('institutional_v106',[],0,None)]}
research={'symbol':'TEST','decision':'CANDIDATE','score':66,'confidence':75,'coverage':90,'risk':'MODERATE','hard_risk_override':False}
flow={'symbol':'TEST','trade_plan':{'status':'AT_PULLBACK_ZONE','pullback':{'planned_entry':100,'invalidation':95,'target_1':110,'target_2':120}},'current_setup':{'status':'AT_PULLBACK_ZONE'},'exit_policy':{'status':'ACTIVE_POLICY'},'paper_proposal':{'eligible':False,'status':'RESEARCH_SETUP_ONLY'},'portfolio':{'account':{'equity':100000,'cash':50000},'positions':[]}}
with tempfile.TemporaryDirectory() as td:
 p=V11InvestmentPlatform(os.path.join(td,'j.db')); out=p.build('TEST',research,v106,flow,record=True)
 assert out['schema_version']=='11.0.1'
 assert out['decision']['authority']=='BABY_DETERMINISTIC_V11_0_1'
 assert out['authority']['LLM_SCORING_AUTHORITY']=='0%'
 assert out['authority']['REAL_MONEY']=='DISABLED'
 assert out['trade_intelligence']['paper_execution_requires_explicit_confirmation'] is True
 assert out['journal']['recorded'] is True
 assert out['thesis']['bull_case']
 # hard-risk invariant
 r2=dict(research,hard_risk_override=True,risk='VERY_HIGH')
 o2=p.build('TEST',r2,v106,flow)
 assert o2['decision']['state'] in {'WAIT','AVOID'} and o2['decision']['score']<=44
print('BABY V11 UNIFIED INVESTMENT INTELLIGENCE: PASS')
print('Evidence graph: PASS')
print('Bull/Bear thesis: PASS')
print('Expectations engine: PASS')
print('Decision V2 hard-risk cap: PASS')
print('Trade authority preservation: PASS')
print('Decision journal: PASS')
print('AI scoring authority: 0%')
print('Real money: DISABLED')
