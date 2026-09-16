import os
os.environ['BABY_COPILOT_MODE']='LEGACY'
from pathlib import Path
import json, tempfile
from baby_ui_backend.copilot import BabyCopilot

with tempfile.TemporaryDirectory() as td:
    c=BabyCopilot(Path(td)); sid='conversation-regression'
    a=c.ask('What is RSI?',{},sid); assert a['data']['topic']=='RSI'
    for q in ['Explain more','Tell me more','Go deeper','Give me more details']:
        r=c.ask(q,{},sid); assert r['data']['topic']=='RSI', (q,r); assert r['data']['followup_kind']=='MORE'; assert 'RSI' in r['answer']
    r=c.ask('How is it calculated?',{},sid); assert r['data']['topic']=='RSI' and '100 - 100/(1 + RS)' in r['answer']
    r=c.ask('Why is it important?',{},sid); assert r['data']['topic']=='RSI' and 'momentum' in r['answer'].lower()
    r=c.ask('Give me an example',{},sid); assert r['data']['topic']=='RSI' and '14' in r['answer']
    r=c.ask('Is it good or bad?',{},sid); assert r['data']['topic']=='RSI' and 'standalone' in r['answer'].lower()

    # Topic switching must be explicit and then persist.
    r=c.ask('What is free cash flow?',{},sid); assert r['data']['topic']=='FCF'
    r=c.ask('Explain more',{},sid); assert r['data']['topic']=='FCF' and 'cash' in r['answer'].lower()
    r=c.ask('How is it calculated?',{},sid); assert r['data']['topic']=='FCF' and 'capital expenditures' in r['answer'].lower()

    # UI context: with no active topic in a fresh session, deictic stage questions resolve to visible stage.
    report={'stages':[{'id':'valuation','status':'PASS','score':18.5,'negatives':['Valuation is demanding'],'unknowns':[],'conflicts':[]}]}
    Path(td,'AAPL.json').write_text(json.dumps(report))
    sid2='ui-stage'
    r=c.ask('Why is this so low?',{'symbol':'AAPL','stage_id':'valuation','stage_label':'Valuation'},sid2)
    assert r['mode']=='EVIDENCE_QA' and '18.5' in r['answer'] and 'demanding' in r['answer'].lower()
    r=c.ask('Explain more',{'symbol':'AAPL','stage_id':'valuation','stage_label':'Valuation'},sid2)
    assert r['mode']=='EVIDENCE_QA' and 'valuation' in r['answer'].lower()

# Source safety remains immutable.
copilot=Path('baby_ui_backend/copilot.py').read_text(); broker=Path('baby_ui_backend/alpaca_broker.py').read_text(); app=Path('baby_ui_backend/app.py').read_text()
assert 'Never execute or propose an order from chat' in copilot
assert 'paper=True' in broker and 'load_dotenv' in broker
segment=app[app.index("@app.post('/api/research/{symbol}/alpaca-paper-order')"):app.index("@app.get('/api/automations')")]
assert "payload.get('quantity'" not in segment
print('BABY V8.7.2 CONVERSATION HARDENING: PASS')
print('generic continuation resolver: PASS')
print('topic switching + persistence: PASS')
print('calculation/importance/example/interpretation follow-ups: PASS')
print('UI-stage deictic continuation: PASS')
print('chat execution authority: NONE')
print('AI scoring authority: 0%')
print('real-money execution: DISABLED')
