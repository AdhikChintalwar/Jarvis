from __future__ import annotations
import json, os, re, threading, time, urllib.request, urllib.error
from pathlib import Path
from dotenv import load_dotenv
from .agent_tools import BabyReadOnlyTools

PROJECT_ROOT=Path(__file__).resolve().parents[1]
load_dotenv(dotenv_path=PROJECT_ROOT/'.env',override=False)

class SessionMemory:
    def __init__(self,ttl=21600,max_turns=16): self.ttl=ttl; self.max_turns=max_turns; self.lock=threading.Lock(); self.data={}
    def get(self,sid):
        with self.lock:
            x=self.data.get(sid,{'turns':[],'state':{}})
            if time.time()-x.get('ts',time.time())>self.ttl:x={'turns':[],'state':{}}
            return {'turns':list(x.get('turns',[])),'state':dict(x.get('state',{}))}
    def put(self,sid,x):
        if not sid:return
        x['turns']=x.get('turns',[])[-self.max_turns:]; x['ts']=time.time()
        with self.lock:self.data[sid]=x

class AgenticProviderError(RuntimeError):
    def __init__(self, kind:str, message:str, status_code:int|None=None):
        super().__init__(message); self.kind=kind; self.status_code=status_code

class BabyAgenticCopilot:
    """AI plans; read-only tools establish facts; AI synthesizes. No scoring or execution tools."""
    def __init__(self,report_dir:Path):
        self.tools=BabyReadOnlyTools(report_dir); self.memory=SessionMemory()
        self._failure_count=0; self._circuit_open_until=0.0; self._last_error=None; self._last_trace=None
    def available(self):
        return bool(os.getenv('NVIDIA_API_KEY')) and time.time() >= self._circuit_open_until
    def configured(self): return bool(os.getenv('NVIDIA_API_KEY'))
    def _endpoint(self):
        base=(os.getenv('NVIDIA_BASE_URL') or 'https://integrate.api.nvidia.com/v1').strip().rstrip('/')
        if base.endswith('/chat/completions'): return base
        return base + '/chat/completions'
    def _model(self): return (os.getenv('NVIDIA_MODEL') or 'nvidia/nemotron-3-ultra-550b-a55b').strip()
    def _record_failure(self, kind, message, status=None):
        self._failure_count += 1
        self._last_error={'kind':kind,'message':str(message),'status_code':status,'at':time.time()}
        threshold=max(1,int(os.getenv('BABY_AGENT_FAILURE_THRESHOLD','1')))
        if self._failure_count >= threshold:
            self._circuit_open_until=time.time()+max(5,int(os.getenv('BABY_AGENT_CIRCUIT_SECONDS','60')))
    def _record_success(self):
        self._failure_count=0; self._circuit_open_until=0.0; self._last_error=None
    def status(self):
        if not self.configured(): state='LEGACY'
        elif time.time() < self._circuit_open_until: state='DEGRADED'
        else: state='AGENTIC'
        return {'state':state,'configured':self.configured(),'provider':'NVIDIA','model':self._model(),
                'endpoint':self._endpoint(),'circuit_open':time.time()<self._circuit_open_until,
                'circuit_retry_after':self._circuit_open_until if time.time()<self._circuit_open_until else None,
                'last_error':self._last_error,'last_trace':self._last_trace,'AI_SCORING_AUTHORITY':'0%','CHAT_EXECUTION_AUTHORITY':'NONE','REAL_MONEY_EXECUTION':'DISABLED'}
    def _chat(self,messages,max_tokens=900,temperature=.1):
        key=os.getenv('NVIDIA_API_KEY')
        if not key: raise AgenticProviderError('NOT_CONFIGURED','NVIDIA_API_KEY is not configured.')
        if time.time() < self._circuit_open_until: raise AgenticProviderError('CIRCUIT_OPEN','Agentic provider is temporarily unavailable.')
        payload={'model':self._model(),'messages':messages,'temperature':temperature,'max_tokens':max_tokens}
        req=urllib.request.Request(self._endpoint(),data=json.dumps(payload).encode(),headers={'Authorization':f'Bearer {key}','Content-Type':'application/json','Accept':'application/json','User-Agent':'BabyInvestor/9.0.2'})
        try:
            with urllib.request.urlopen(req,timeout=float(os.getenv('BABY_AGENT_TIMEOUT_SECONDS','30'))) as r:
                d=json.loads(r.read().decode())
            out=d['choices'][0]['message']['content'].strip(); self._record_success(); return out
        except urllib.error.HTTPError as e:
            try: body=e.read().decode(errors='replace')[:800]
            except Exception: body=''
            kind={401:'AUTHENTICATION',403:'AUTHORIZATION',404:'ENDPOINT_OR_MODEL',429:'RATE_LIMIT'}.get(e.code,'HTTP_ERROR')
            msg=f'NVIDIA provider HTTP {e.code} ({kind}).' + (f' {body}' if body else '')
            self._record_failure(kind,msg,e.code); raise AgenticProviderError(kind,msg,e.code) from e
        except urllib.error.URLError as e:
            msg=f'NVIDIA provider network error: {e.reason}'; self._record_failure('NETWORK',msg); raise AgenticProviderError('NETWORK',msg) from e
        except TimeoutError as e:
            msg='NVIDIA provider timed out.'; self._record_failure('TIMEOUT',msg); raise AgenticProviderError('TIMEOUT',msg) from e
        except (KeyError,IndexError,TypeError,json.JSONDecodeError) as e:
            msg=f'NVIDIA provider returned an invalid response: {e}'; self._record_failure('INVALID_RESPONSE',msg); raise AgenticProviderError('INVALID_RESPONSE',msg) from e
    def _json(self,text):
        """Extract one complete JSON object from model output, including fenced/nested JSON.

        V9.0.1 used a non-greedy regex for fenced JSON. Nested planner objects such as
        entities/tool_calls caused that regex to stop at the first closing brace and
        silently pushed healthy agentic requests into legacy fallback.
        """
        if isinstance(text,dict): return text
        t=str(text or '').strip()
        # Strip only the fence markers; never regex-match a nested object non-greedily.
        if t.startswith('```'):
            t=re.sub(r'^```(?:json)?\s*','',t,flags=re.I)
            t=re.sub(r'\s*```$','',t)
        decoder=json.JSONDecoder()
        # Fast path: exact JSON.
        try:
            obj=decoder.decode(t)
            if isinstance(obj,dict): return obj
        except json.JSONDecodeError:
            pass
        # Robust path: find the first decodable JSON object, respecting nested braces,
        # strings and escapes through JSONDecoder.raw_decode.
        for i,ch in enumerate(t):
            if ch!='{': continue
            try:
                obj,_=decoder.raw_decode(t[i:])
                if isinstance(obj,dict): return obj
            except json.JSONDecodeError:
                continue
        raise AgenticProviderError('INVALID_PLANNER_JSON','Nemotron planner did not return a complete JSON object.')

    def _validate_plan(self,plan):
        if not isinstance(plan,dict): raise AgenticProviderError('INVALID_PLAN','Planner result is not an object.')
        mode=str(plan.get('response_mode') or 'GENERAL').upper()
        allowed_modes={'GENERAL','EDUCATION','MARKET_QUOTE','MARKET_UPDATE','COMPANY_RESEARCH','BABY_EVIDENCE','SCREENER'}
        if mode not in allowed_modes: mode='GENERAL'
        calls=plan.get('tool_calls')
        if calls is None: calls=[]
        if not isinstance(calls,list): raise AgenticProviderError('INVALID_PLAN','tool_calls must be a list.')
        plan['tool_calls']=calls[:5]; plan['response_mode']=mode
        plan['needs_tools']=bool(plan.get('needs_tools') or calls)
        if not isinstance(plan.get('entities'),dict): plan['entities']={}
        if not isinstance(plan.get('state_updates'),dict): plan['state_updates']={}
        return plan

    def _planner(self,message,history,state,ui):
        schema=json.dumps(self.tools.schemas(),separators=(',',':'))
        system='''You are Baby's planning brain for an investment research copilot. Understand natural conversation, typos, pronouns, company names and follow-ups. Decide whether tools are required. Fresh/current/today/recent/company-specific factual questions MUST use tools. General greetings/chitchat and timeless education can answer without tools. Never guess a current fact. Never request or call any order/broker execution tool. Never alter Baby scores/risk/trade plans. Return JSON only: {"intent":"...","entities":{"symbol_or_company":"..."},"needs_tools":true/false,"tool_calls":[{"name":"...","args":{}}],"response_mode":"GENERAL|EDUCATION|MARKET_QUOTE|MARKET_UPDATE|COMPANY_RESEARCH|BABY_EVIDENCE|SCREENER","state_updates":{}}. Use at most 5 tool calls. For broad recent market updates use get_market_context + get_market_news. For company news use get_company_news and usually get_quote. For a current price use get_quote. For Baby's own analysis use get_baby_research. A phrase like "how about Tesla stock" after a quote means Tesla/TSLA and usually requests the same quote intent. Explicit new entities override stale UI context.'''
        user={'message':message,'recent_turns':history[-6:],'conversation_state':state,'ui_context':ui,'tools':json.loads(schema)}
        return self._validate_plan(self._json(self._chat([{'role':'system','content':system},{'role':'user','content':json.dumps(user)}],650,0)))
    def _synthesize(self,message,plan,results,history,state):
        system='''You are Baby, a capable conversational investment research assistant. Answer naturally and directly. Tool results are the factual authority for current/company facts. Do not invent facts not present in tool evidence. If evidence is missing, say it is unknown/not found. Distinguish IEX from consolidated SIP. News summaries must identify source and time when available and must not claim a news item caused a price move unless evidence establishes that; say "may be relevant" or "possible catalyst" when appropriate. Baby deterministic research scores/risk are authoritative when present; you may explain them but never change them. Do not give a buy/sell verdict or execute/propose orders from chat. AI scoring authority 0%; chat execution authority NONE. For greetings and ordinary conversation, respond normally rather than giving a glossary fallback. Keep answers concise unless the user asks for depth.'''
        payload={'question':message,'plan':plan,'tool_evidence':results,'recent_turns':history[-6:],'state':state}
        return self._chat([{'role':'system','content':system},{'role':'user','content':json.dumps(payload,default=str)}],1100,.15)
    def ask(self,message:str,context:dict|None=None,session_id:str|None=None):
        text=(message or '').strip(); context=context or {}
        if not text: raise ValueError('message is required')
        mem=self.memory.get(session_id); state=mem['state']; history=mem['turns']
        # UI context is advisory only; explicit conversation can override it.
        ui={k:context.get(k) for k in ('symbol','stage_id','stage_label','page') if context.get(k) not in (None,'')}
        self._last_trace={'phase':'PLANNING','message_preview':text[:120],'at':time.time()}
        try: plan=self._planner(text,history,state,ui)
        except Exception as e:
            self._last_trace={'phase':'PLANNER_FAILED','error_type':type(e).__name__,'error':str(e)[:500],'at':time.time()}
            raise RuntimeError(f'Agent planner failed: {e}')
        self._last_trace={'phase':'PLANNED','intent':plan.get('intent'),'response_mode':plan.get('response_mode'),'tool_calls':[str(x.get('name')) for x in (plan.get('tool_calls') or [])],'at':time.time()}
        calls=plan.get('tool_calls') or []; results=[]
        allowed={x['name'] for x in self.tools.schemas()}
        for c in calls[:5]:
            name=str(c.get('name') or '')
            if name not in allowed:
                results.append({'tool':name,'ok':False,'error':'Tool is not in Baby read-only registry.'}); continue
            try: results.append({'tool':name,'ok':True,'data':self.tools.call(name,c.get('args') or {})})
            except Exception as e: results.append({'tool':name,'ok':False,'error':str(e)})
        try: answer=self._synthesize(text,plan,results,history,state)
        except Exception as e:
            self._last_trace={'phase':'SYNTHESIS_FAILED','intent':plan.get('intent'),'error_type':type(e).__name__,'error':str(e)[:500],'at':time.time()}
            raise RuntimeError(f'Agent synthesis failed: {e}')
        self._last_trace={'phase':'COMPLETE','intent':plan.get('intent'),'response_mode':plan.get('response_mode'),'tool_calls':[r.get('tool') for r in results],'at':time.time()}
        updates=plan.get('state_updates') or {}; state.update({k:v for k,v in updates.items() if k in {'active_symbol','active_topic','active_stage','active_filters','previous_intent'} and v is not None})
        ent=(plan.get('entities') or {}).get('symbol_or_company')
        # Promote a verified resolved symbol from tool evidence into conversation state.
        for r in results:
            d=r.get('data') or {}
            if r.get('ok') and isinstance(d,dict) and d.get('symbol'): state['active_symbol']=d['symbol']
        state['previous_intent']=plan.get('intent') or state.get('previous_intent')
        history.extend([{'role':'user','content':text},{'role':'assistant','content':answer,'mode':plan.get('response_mode')}])
        mem={'turns':history,'state':state}; self.memory.put(session_id,mem)
        evidence=[]
        for r in results:
            if not r.get('ok'):continue
            d=r.get('data') or {}; src=d.get('source') or d.get('provider')
            if src:evidence.append({'label':str(src)+(f" · {d.get('feed')}" if d.get('feed') else ''),'kind':'TOOL_EVIDENCE'})
        data={'plan':plan,'tool_results':results,'agentic':True,'authority':{'AI_SCORING':'0%','CHAT_EXECUTION':'NONE','REAL_MONEY':'DISABLED'}}
        # Preserve quote-card compatibility.
        for r in results:
            d=r.get('data') or {}
            if r.get('tool')=='get_quote' and r.get('ok') and d.get('price') is not None: data={**data,**d}; break
        return {'mode':plan.get('response_mode') or 'BABY','answer':answer,'data':data,'evidence':evidence,'context_state':state,'agentic':True}
