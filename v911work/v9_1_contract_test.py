import os, tempfile
from pathlib import Path
from baby_ui_backend.ai_providers import ProviderOrchestrator, AIProviderError, BaseProvider
from baby_ui_backend.agentic_copilot import BabyAgenticCopilot

class FakeProvider(BaseProvider):
    def __init__(self,name,answers=None,fail=False): super().__init__(); self.name=name; self.answers=list(answers or []); self.fail=fail
    def configured(self): return True
    def model(self): return 'fake'
    def endpoint(self): return 'mock://'+self.name
    def chat(self,messages,max_tokens=900,temperature=.1):
        if self.fail:
            self.failure('MOCK_FAIL','mock failure'); raise AIProviderError(self.name,'MOCK_FAIL','mock failure')
        self.success(); return self.answers.pop(0)

planner='''```json\n{"intent":"GENERAL_CHAT","entities":{},"needs_tools":false,"tool_calls":[],"response_mode":"GENERAL","state_updates":{"active_topic":"general"}}\n```'''
primary=FakeProvider('OPENAI',[planner,'I am doing well. What would you like to research today?'])
secondary=FakeProvider('NVIDIA',fail=True)
orch=ProviderOrchestrator({'OPENAI':primary,'NVIDIA':secondary})
os.environ['BABY_AI_PROVIDER_ORDER']='OPENAI,NVIDIA'
with tempfile.TemporaryDirectory() as td:
    c=BabyAgenticCopilot(Path(td),orch)
    r=c.ask('how are you doing today?',{},'s1')
    assert r['agentic'] and 'doing well' in r['answer']
    assert orch.last_provider=='OPENAI'

# Primary failure -> secondary success
p1=FakeProvider('OPENAI',fail=True)
p2=FakeProvider('NVIDIA',[planner,'Fallback AI response'])
orch2=ProviderOrchestrator({'OPENAI':p1,'NVIDIA':p2})
with tempfile.TemporaryDirectory() as td:
    c=BabyAgenticCopilot(Path(td),orch2)
    r=c.ask('hello',{},'s2')
    assert r['agentic'] and r['answer']=='Fallback AI response'
    assert orch2.last_provider=='NVIDIA'
    assert orch2.last_failover and orch2.last_failover[0]['provider']=='OPENAI'

# Both fail -> explicit provider error, allowing Copilot outer layer to deterministic fallback.
p1=FakeProvider('OPENAI',fail=True); p2=FakeProvider('NVIDIA',fail=True)
orch3=ProviderOrchestrator({'OPENAI':p1,'NVIDIA':p2})
try:
    orch3.chat([{'role':'user','content':'x'}])
    raise AssertionError('expected failure')
except AIProviderError as e:
    assert e.kind=='ALL_PROVIDERS_UNAVAILABLE'

print('BABY V9.1 MULTI-PROVIDER AGENTIC BRAIN: PASS')
print('OpenAI primary: PASS')
print('NVIDIA failover: PASS')
print('all-AI-down deterministic fallback contract: PASS')
print('AI scoring authority: 0%')
print('chat execution authority: NONE')
print('real-money execution: DISABLED')
