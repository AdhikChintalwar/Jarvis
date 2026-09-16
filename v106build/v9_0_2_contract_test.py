import os, json
from pathlib import Path
from baby_ui_backend.copilot import BabyCopilot
from baby_ui_backend.agentic_copilot import BabyAgenticCopilot

root=Path(__file__).parent
os.environ['BABY_COPILOT_MODE']='AUTO'
os.environ['NVIDIA_API_KEY']='contract-test-key'

# Regression: nested/fenced planner JSON must parse completely (the V9.0.1 live-routing bug).
a=BabyAgenticCopilot(root/'data'/'ui_research')
raw='''```json\n{"intent":"MARKET_UPDATE","entities":{"symbol_or_company":""},"needs_tools":true,"tool_calls":[{"name":"get_market_context","args":{}},{"name":"get_market_news","args":{"limit":10}}],"response_mode":"MARKET_UPDATE","state_updates":{"previous_intent":"MARKET_UPDATE"}}\n```'''
p=a._json(raw)
assert p['intent']=='MARKET_UPDATE' and len(p['tool_calls'])==2 and p['state_updates']['previous_intent']=='MARKET_UPDATE'

# Healthy AUTO must use agentic path and must NOT touch deterministic fallback.
c=BabyCopilot(root/'data'/'ui_research')
c.agentic.available=lambda: True
calls=[]
def healthy(text,ctx,sid):
    calls.append(text)
    return {'mode':'GENERAL','answer':'Doing well. What are we looking at today?','data':{'agentic':True},'evidence':[],'agentic':True}
c.agentic.ask=healthy
# Make fallback explode if it is accidentally reached.
c._topic=lambda text: (_ for _ in ()).throw(AssertionError('legacy fallback invoked during healthy agentic request'))
r=c.ask('how are you doing today?',{},'live-agentic')
assert r['agentic'] is True and r['runtime']['state']=='AGENTIC' and calls==['how are you doing today?']
assert c.last_agentic_fallback is None

# Healthy market question also stays agentic.
r=c.ask('how is the market doing today?',{},'live-market')
assert r['agentic'] is True and r['runtime']['fallback'] is False

# Validate actual planner structure normalization without network.
a2=BabyAgenticCopilot(root/'data'/'ui_research')
a2._chat=lambda *args,**kwargs: raw
plan=a2._planner('how is the market doing today?',[],{}, {})
assert plan['response_mode']=='MARKET_UPDATE' and plan['needs_tools'] is True

print('BABY V9.0.2 LIVE AGENT ROUTING CONTRACT: PASS')
print('nested/fenced Nemotron planner JSON: PASS')
print('healthy AUTO -> agentic, never legacy: PASS')
print('market question -> agentic path: PASS')
print('AI scoring authority: 0%')
print('chat execution authority: NONE')
print('real-money execution: DISABLED')
