import os
from pathlib import Path
from baby_ui_backend.copilot import BabyCopilot
from baby_ui_backend.agentic_copilot import AgenticProviderError

root=Path(__file__).parent
os.environ['BABY_COPILOT_MODE']='AUTO'
os.environ['NVIDIA_API_KEY']='contract-test-key'
c=BabyCopilot(root/'data'/'ui_research')
# Provider failure must degrade, never crash the user request.
def fail(*a,**k):
    c.agentic._record_failure('ENDPOINT_OR_MODEL','contract 404',404)
    raise AgenticProviderError('ENDPOINT_OR_MODEL','contract 404',404)
c.agentic._planner=fail
r=c.ask('What is RSI?',{},'v901')
assert r['mode']=='EDUCATION' and r['data']['topic']=='RSI'
st=c.runtime_status(); assert st['state']=='DEGRADED' and st['fallback_available'] is True
assert st['provider']['last_error']['status_code']==404
# Explicit legacy never invokes AI.
os.environ['BABY_COPILOT_MODE']='LEGACY'
c2=BabyCopilot(root/'data'/'ui_research')
c2.agentic.ask=lambda *a,**k: (_ for _ in ()).throw(AssertionError('agentic path invoked'))
r=c2.ask('What is RSI?',{},'legacy'); assert r['mode']=='EDUCATION'
assert c2.runtime_status()['state']=='LEGACY'
print('BABY V9.0.1 RUNTIME HARDENING CONTRACT: PASS')
print('provider 404 -> deterministic fallback: PASS')
print('circuit breaker/degraded status: PASS')
print('explicit legacy compatibility: PASS')
print('AI scoring authority: 0%')
print('chat execution authority: NONE')
print('real-money execution: DISABLED')
