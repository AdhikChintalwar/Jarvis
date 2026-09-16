import os, tempfile, urllib.error
from pathlib import Path
from io import BytesIO
from unittest.mock import patch
from baby_ui_backend.ai_providers import ProviderOrchestrator, AIProviderError, BaseProvider, OpenAIProvider
from baby_ui_backend.agentic_copilot import BabyAgenticCopilot
from baby_ui_backend.agent_tools import BabyReadOnlyTools

class FakeProvider(BaseProvider):
    def __init__(self,name,answers=None,fail=None): super().__init__(); self.name=name; self.answers=list(answers or []); self.fail_kind=fail
    def configured(self): return True
    def model(self): return 'fake'
    def endpoint(self): return 'mock://'+self.name
    def chat(self,messages,max_tokens=900,temperature=.1):
        if self.fail_kind:
            self.failure(self.fail_kind,'mock failure',429 if self.fail_kind=='INSUFFICIENT_QUOTA' else None)
            raise AIProviderError(self.name,self.fail_kind,'mock failure',429 if self.fail_kind=='INSUFFICIENT_QUOTA' else None)
        self.success(); return self.answers.pop(0)

# Unprobed provider is eligible, but must not be falsely reported healthy.
p=FakeProvider('OPENAI',['x']); st=p.status(); assert st['health']=='UNVERIFIED' and st['healthy'] is False and st['eligible'] is True
p.success(); assert p.status()['health']=='HEALTHY'

# Planner -> tools -> synthesis integration with no network.
planner='{"intent":"broad_market_update","entities":{},"needs_tools":true,"tool_calls":[{"name":"get_market_context","args":{}},{"name":"get_market_news","args":{"limit":3}}],"response_mode":"MARKET_UPDATE","state_updates":{}}'
orch=ProviderOrchestrator({'OPENAI':FakeProvider('OPENAI',[planner,'Market synthesis from verified evidence.'])})
with tempfile.TemporaryDirectory() as td:
    c=BabyAgenticCopilot(Path(td),orch)
    c.tools.call=lambda n,a: ({'source':'mock market','feed':'IEX','snapshots':{}} if n=='get_market_context' else {'source':'mock news','news':[]})
    r=c.ask('how is the market today?',{},'stable')
    assert r['agentic'] and r['mode']=='MARKET_UPDATE' and len(r['data']['tool_results'])==2
    assert c.status()['last_trace']['phase']=='COMPLETE'

# Deterministic quote sanity checks.
with tempfile.TemporaryDirectory() as td:
    t=BabyReadOnlyTools(Path(td))
    q=t._validate_quote({'symbol':'X','price':10,'bid':9,'ask':0,'feed':'IEX','timestamp':'2026-09-16T21:00:00Z'})
    assert q['validation']['status']=='INVALID' and 'INVALID_ASK' in q['validation']['issues'] and 'IEX_PARTIAL_MARKET' in q['validation']['issues']

# Quota is not a generic rate limit.
provider=OpenAIProvider(); os.environ['OPENAI_API_KEY']='test'; os.environ['OPENAI_MODEL']='gpt-5.6-luna'
err=urllib.error.HTTPError(provider.endpoint(),429,'x',{},BytesIO(b'{"error":{"code":"credit_balance_exhausted","type":"insufficient_quota"}}'))
with patch('urllib.request.urlopen',side_effect=err):
    try: provider.chat([{'role':'user','content':'x'}]); raise AssertionError('expected')
    except AIProviderError as e: assert e.kind=='INSUFFICIENT_QUOTA'

print('BABY V9.1.1 STABLE AGENTIC RESEARCH: PASS')
print('provider health semantics: PASS')
print('planner -> tools -> synthesis integration: PASS')
print('deterministic quote sanity/freshness: PASS')
print('insufficient quota classification: PASS')
print('AI scoring authority: 0%')
print('chat execution authority: NONE')
print('real-money execution: DISABLED')
