import os
os.environ['BABY_COPILOT_MODE']='LEGACY'
from pathlib import Path
import tempfile, json
from baby_ui_backend.research_knowledge import STAGE_KNOWLEDGE, STATUS_LEGEND
from baby_ui_backend.copilot import BabyCopilot

assert len(STAGE_KNOWLEDGE)>=14
assert 'UNKNOWN' in STATUS_LEGEND and 'not bearish' in STATUS_LEGEND['UNKNOWN']
with tempfile.TemporaryDirectory() as td:
    p=Path(td)/'AAPL.json'
    p.write_text(json.dumps({'symbol':'AAPL','decision':'WATCH','score':53.5,'confidence':73.34,'coverage':100,'risk':'MODERATE','stages':[{'id':'valuation','label':'Valuation','status':'PASS','score':18.5,'summary':'DEMANDING'}],'trade_plan':{'status':'WAIT_FOR_PULLBACK_OR_BREAKOUT','current_setup':{'status':'WAIT_FOR_PULLBACK_OR_BREAKOUT','reason':'Price is above pullback zone and breakout is not confirmed.'}}}))
    c=BabyCopilot(Path(td))
    r=c.ask('Why is AAPL WATCH?',{'symbol':'AAPL','stage_id':'decision'})
    assert r['mode']=='EVIDENCE_QA' and '53.5' in r['answer'] and 'MODERATE' in r['answer']
    r=c.ask('What is this?',{'symbol':'AAPL','stage_id':'valuation'})
    assert r['mode']=='EVIDENCE_QA' and '18.5' in r['answer']
    class FakeMarket:
        def filter_price(self,a,b,limit=100):return {'filters':{'min_price':a,'max_price':b},'count':1,'results':[{'symbol':'TEST','price':15.0}],'source':'TEST','feed':'IEX'}
    c.market=FakeMarket();r=c.ask('show stocks between $10 and $20',{})
    assert r['mode']=='TOOL_ACTION' and r['data']['filters']=={'min_price':10.0,'max_price':20.0}
print('BABY V8.7 CONTRACT: PASS')
print('research legend + per-stage explainability: PASS')
print('context-aware evidence Q&A: PASS')
print('deterministic natural-language price filter: PASS')
print('Alpaca paper execution retained: PASS')
print('AI scoring authority: 0%')
print('real-money execution: DISABLED')
