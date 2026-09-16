from __future__ import annotations
import json, os, time, urllib.request, urllib.error
from dataclasses import dataclass

class AIProviderError(RuntimeError):
    def __init__(self, provider:str, kind:str, message:str, status_code:int|None=None):
        super().__init__(message); self.provider=provider; self.kind=kind; self.status_code=status_code

@dataclass
class ProviderState:
    failures:int=0
    open_until:float=0.0
    last_error:dict|None=None
    last_success_at:float|None=None

class BaseProvider:
    name='BASE'
    def __init__(self): self.state=ProviderState()
    def configured(self)->bool: return False
    def model(self)->str: return ''
    def endpoint(self)->str: return ''
    def _threshold(self): return max(1,int(os.getenv('BABY_AI_FAILURE_THRESHOLD','1')))
    def _cooldown(self): return max(5,int(os.getenv('BABY_AI_CIRCUIT_SECONDS','60')))
    def circuit_open(self): return time.time()<self.state.open_until
    def available(self): return self.configured() and not self.circuit_open()
    def success(self):
        self.state.failures=0; self.state.open_until=0.0; self.state.last_error=None; self.state.last_success_at=time.time()
    def failure(self,kind,msg,status=None):
        self.state.failures+=1; self.state.last_error={'kind':kind,'message':str(msg)[:800],'status_code':status,'at':time.time()}
        if self.state.failures>=self._threshold(): self.state.open_until=time.time()+self._cooldown()
    def status(self):
        return {'provider':self.name,'configured':self.configured(),'healthy':self.available(),'model':self.model(),'endpoint':self.endpoint(),
                'circuit_open':self.circuit_open(),'circuit_retry_after':self.state.open_until if self.circuit_open() else None,
                'last_error':self.state.last_error,'last_success_at':self.state.last_success_at}
    def chat(self,messages,max_tokens=900,temperature=.1): raise NotImplementedError

class OpenAIProvider(BaseProvider):
    name='OPENAI'
    def configured(self): return bool(os.getenv('OPENAI_API_KEY'))
    def model(self): return (os.getenv('OPENAI_MODEL') or 'gpt-5.6-luna').strip()
    def endpoint(self):
        base=(os.getenv('OPENAI_BASE_URL') or 'https://api.openai.com/v1').strip().rstrip('/')
        return base if base.endswith('/responses') else base+'/responses'
    def chat(self,messages,max_tokens=900,temperature=.1):
        key=os.getenv('OPENAI_API_KEY')
        if not key: raise AIProviderError(self.name,'NOT_CONFIGURED','OPENAI_API_KEY is not configured.')
        if self.circuit_open(): raise AIProviderError(self.name,'CIRCUIT_OPEN','OpenAI provider circuit is temporarily open.')
        # Responses API: preserve roles; output_text is reconstructed from output content for raw HTTP compatibility.
        payload={'model':self.model(),'input':messages,'max_output_tokens':max_tokens}
        req=urllib.request.Request(self.endpoint(),data=json.dumps(payload).encode(),headers={'Authorization':f'Bearer {key}','Content-Type':'application/json','Accept':'application/json','User-Agent':'BabyInvestor/9.1'})
        try:
            with urllib.request.urlopen(req,timeout=float(os.getenv('BABY_AI_TIMEOUT_SECONDS','45'))) as r: d=json.loads(r.read().decode())
            text=d.get('output_text')
            if not text:
                parts=[]
                for item in d.get('output') or []:
                    if item.get('type')=='message':
                        for c in item.get('content') or []:
                            if c.get('type') in ('output_text','text') and c.get('text'): parts.append(c['text'])
                text=''.join(parts)
            if not text: raise KeyError('No text output in Responses API response')
            self.success(); return text.strip()
        except urllib.error.HTTPError as e:
            try: body=e.read().decode(errors='replace')[:800]
            except Exception: body=''
            kind={400:'BAD_REQUEST',401:'AUTHENTICATION',403:'AUTHORIZATION',404:'ENDPOINT_OR_MODEL',429:'RATE_LIMIT'}.get(e.code,'PROVIDER_UNAVAILABLE' if e.code>=500 else 'HTTP_ERROR')
            msg=f'OpenAI HTTP {e.code} ({kind}).'+(f' {body}' if body else '')
            self.failure(kind,msg,e.code); raise AIProviderError(self.name,kind,msg,e.code) from e
        except urllib.error.URLError as e:
            msg=f'OpenAI network error: {e.reason}'; self.failure('NETWORK',msg); raise AIProviderError(self.name,'NETWORK',msg) from e
        except TimeoutError as e:
            msg='OpenAI request timed out.'; self.failure('TIMEOUT',msg); raise AIProviderError(self.name,'TIMEOUT',msg) from e
        except (KeyError,IndexError,TypeError,json.JSONDecodeError) as e:
            msg=f'OpenAI returned an invalid response: {e}'; self.failure('INVALID_RESPONSE',msg); raise AIProviderError(self.name,'INVALID_RESPONSE',msg) from e

class NvidiaProvider(BaseProvider):
    name='NVIDIA'
    def configured(self): return bool(os.getenv('NVIDIA_API_KEY'))
    def model(self): return (os.getenv('NVIDIA_MODEL') or 'nvidia/nemotron-3-ultra-550b-a55b').strip()
    def endpoint(self):
        base=(os.getenv('NVIDIA_BASE_URL') or 'https://integrate.api.nvidia.com/v1').strip().rstrip('/')
        return base if base.endswith('/chat/completions') else base+'/chat/completions'
    def chat(self,messages,max_tokens=900,temperature=.1):
        key=os.getenv('NVIDIA_API_KEY')
        if not key: raise AIProviderError(self.name,'NOT_CONFIGURED','NVIDIA_API_KEY is not configured.')
        if self.circuit_open(): raise AIProviderError(self.name,'CIRCUIT_OPEN','NVIDIA provider circuit is temporarily open.')
        payload={'model':self.model(),'messages':messages,'temperature':temperature,'max_tokens':max_tokens}
        req=urllib.request.Request(self.endpoint(),data=json.dumps(payload).encode(),headers={'Authorization':f'Bearer {key}','Content-Type':'application/json','Accept':'application/json','User-Agent':'BabyInvestor/9.1'})
        try:
            with urllib.request.urlopen(req,timeout=float(os.getenv('BABY_AI_TIMEOUT_SECONDS','45'))) as r: d=json.loads(r.read().decode())
            text=d['choices'][0]['message']['content']; self.success(); return text.strip()
        except urllib.error.HTTPError as e:
            try: body=e.read().decode(errors='replace')[:800]
            except Exception: body=''
            kind={401:'AUTHENTICATION',403:'AUTHORIZATION',404:'ENDPOINT_OR_MODEL',429:'RATE_LIMIT'}.get(e.code,'PROVIDER_UNAVAILABLE' if e.code>=500 else 'HTTP_ERROR')
            msg=f'NVIDIA HTTP {e.code} ({kind}).'+(f' {body}' if body else '')
            self.failure(kind,msg,e.code); raise AIProviderError(self.name,kind,msg,e.code) from e
        except urllib.error.URLError as e:
            msg=f'NVIDIA network error: {e.reason}'; self.failure('NETWORK',msg); raise AIProviderError(self.name,'NETWORK',msg) from e
        except TimeoutError as e:
            msg='NVIDIA request timed out.'; self.failure('TIMEOUT',msg); raise AIProviderError(self.name,'TIMEOUT',msg) from e
        except (KeyError,IndexError,TypeError,json.JSONDecodeError) as e:
            msg=f'NVIDIA returned an invalid response: {e}'; self.failure('INVALID_RESPONSE',msg); raise AIProviderError(self.name,'INVALID_RESPONSE',msg) from e

class ProviderOrchestrator:
    def __init__(self,providers=None):
        self.providers=providers or {'OPENAI':OpenAIProvider(),'NVIDIA':NvidiaProvider()}
        self.last_provider=None; self.last_failover=[]
    def order(self):
        raw=(os.getenv('BABY_AI_PROVIDER_ORDER') or 'OPENAI,NVIDIA').upper()
        names=[x.strip() for x in raw.split(',') if x.strip()]
        return [x for x in names if x in self.providers]
    def configured(self): return any(p.configured() for p in self.providers.values())
    def available(self): return any(self.providers[n].available() for n in self.order())
    def chat(self,messages,max_tokens=900,temperature=.1):
        failures=[]
        for name in self.order():
            p=self.providers[name]
            if not p.configured(): continue
            if p.circuit_open():
                failures.append({'provider':name,'kind':'CIRCUIT_OPEN'}); continue
            try:
                out=p.chat(messages,max_tokens,temperature); self.last_provider=name; self.last_failover=failures; return out
            except AIProviderError as e:
                failures.append({'provider':name,'kind':e.kind,'status_code':e.status_code})
        self.last_failover=failures
        raise AIProviderError('ORCHESTRATOR','ALL_PROVIDERS_UNAVAILABLE',f'All configured AI providers unavailable: {failures}')
    def status(self):
        states={name:p.status() for name,p in self.providers.items()}
        active=next((n for n in self.order() if self.providers[n].available()),None)
        return {'state':'AGENTIC' if active else ('DEGRADED' if self.configured() else 'LEGACY'),
                'active_provider':active,'preferred_order':self.order(),'last_provider':self.last_provider,
                'last_failover':self.last_failover,'providers':states,
                'AI_SCORING_AUTHORITY':'0%','CHAT_EXECUTION_AUTHORITY':'NONE','REAL_MONEY_EXECUTION':'DISABLED'}
