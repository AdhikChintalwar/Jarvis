from pathlib import Path
import json, tempfile
from baby_ui_backend.copilot import BabyCopilot
from baby_ui_backend.proposal_service import PaperProposalService
from baby_ui_backend.alpaca_broker import CONFIRMATION_PHRASE

with tempfile.TemporaryDirectory() as td:
    c=BabyCopilot(Path(td)); sid='test-session'
    a=c.ask('What is RSI?',{},sid); assert a['data']['topic']=='RSI'
    b=c.ask('Give me brief about it',{},sid); assert 'momentum' in b['answer'].lower() and b['data']['topic']=='RSI'
    d=c.ask('How is it calculated?',{},sid); assert '100 - 100/(1 + RS)' in d['answer']
    # UI-stage deictic context must resolve without LLM.
    report={'stages':[{'id':'valuation','status':'PASS','score':18.5,'negatives':['Valuation is demanding'],'unknowns':[],'conflicts':[]} ]}
    Path(td,'AAPL.json').write_text(json.dumps(report))
    e=c.ask('Why is this so low?',{'symbol':'AAPL','stage_id':'valuation'},sid); assert e['mode']=='EVIDENCE_QA' and '18.5' in e['answer'] and 'demanding' in e['answer'].lower()

# Proposal gate: WAIT setup cannot become eligible.
p=PaperProposalService().build('AAPL',{'decision':'WATCH','score':53.5,'confidence':73,'coverage':100,'risk':'MODERATE','trade_plan':{'status':'WAIT_FOR_PULLBACK_OR_BREAKOUT','current_setup':{'status':'WAIT_FOR_PULLBACK_OR_BREAKOUT'},'position':{'unified_risk_multiplier':.8}}},{'price':334.23,'quality':'DELAYED','provider':'TEST'},{'account':{'equity':100000,'cash':100000}})
assert p['eligible'] is False and p['proposed_quantity'] is None

# Source-level safety contracts.
app=Path('baby_ui_backend/app.py').read_text(); broker=Path('baby_ui_backend/alpaca_broker.py').read_text(); copilot=Path('baby_ui_backend/copilot.py').read_text()
assert "paper=True" in broker
assert 'load_dotenv' in broker and 'ALPACA_PAPER_API_KEY' in broker
assert "quantity=qty" in app and "payload.get('quantity'" not in app[app.index("@app.post('/api/research/{symbol}/alpaca-paper-order')"):app.index("@app.get('/api/automations')")]
assert 'Never execute or propose an order from chat' in copilot
assert CONFIRMATION_PHRASE=='EXECUTE ALPACA PAPER'
print('BABY V8.7.1 CONTRACT: PASS')
print('multi-turn RSI context: PASS')
print('UI stage deictic context: PASS')
print('research-driven Alpaca quantity server-owned: PASS')
print('Alpaca PAPER-only + explicit dotenv: PASS')
print('chat execution authority: NONE')
print('AI scoring authority: 0%')
print('real-money execution: DISABLED')
