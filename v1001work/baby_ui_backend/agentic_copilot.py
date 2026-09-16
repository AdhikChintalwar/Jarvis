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

from .ai_providers import ProviderOrchestrator, AIProviderError

class AgenticProviderError(AIProviderError):
    """Backward-compatible V9 error: (kind, message, status_code)."""
    def __init__(self, kind:str, message:str, status_code:int|None=None):
        super().__init__('AGENTIC',kind,message,status_code)

class BabyAgenticCopilot:
    """Provider-independent AI planner/synthesizer. Read-only tools establish facts."""
    def __init__(self,report_dir:Path, provider_orchestrator=None):
        self.tools=BabyReadOnlyTools(report_dir); self.memory=SessionMemory()
        self.ai=provider_orchestrator or ProviderOrchestrator(); self._last_trace=None
    def available(self): return self.ai.available()
    def configured(self): return self.ai.configured()
    def _record_failure(self,kind,message,status=None):
        # Compatibility shim for V9.0.1 tests/tools; record against the first configured provider.
        for name in self.ai.order():
            p=self.ai.providers[name]
            if p.configured(): p.failure(kind,message,status); return
    def _record_success(self):
        for name in self.ai.order():
            p=self.ai.providers[name]
            if p.configured(): p.success(); return
    def status(self):
        out=self.ai.status(); out['last_trace']=self._last_trace
        # Preserve V9.0.x top-level provider diagnostics while exposing V9.1 per-provider states.
        active_name=out.get('active_provider') or out.get('last_provider')
        if not active_name:
            active_name=next((n for n in out.get('preferred_order',[]) if out['providers'].get(n,{}).get('configured')),None)
        active=out.get('providers',{}).get(active_name,{}) if active_name else {}
        out['configured']=self.configured(); out['last_error']=active.get('last_error')
        out['circuit_open']=active.get('circuit_open',False); out['model']=active.get('model'); out['endpoint']=active.get('endpoint')
        return out
    def _chat(self,messages,max_tokens=900,temperature=.1):
        return self.ai.chat(messages,max_tokens=max_tokens,temperature=temperature)
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
        raise ValueError('AI planner did not return a complete JSON object.')

    def _validate_plan(self,plan):
        if not isinstance(plan,dict): raise ValueError('Planner result is not an object.')
        mode=str(plan.get('response_mode') or 'GENERAL').upper()
        allowed_modes={'GENERAL','EDUCATION','MARKET_QUOTE','MARKET_UPDATE','COMPANY_RESEARCH','BABY_EVIDENCE','SCREENER'}
        if mode not in allowed_modes: mode='GENERAL'
        calls=plan.get('tool_calls')
        if calls is None: calls=[]
        if not isinstance(calls,list): raise ValueError('tool_calls must be a list.')
        plan['tool_calls']=calls[:5]; plan['response_mode']=mode
        plan['needs_tools']=bool(plan.get('needs_tools') or calls)
        if not isinstance(plan.get('entities'),dict): plan['entities']={}
        if not isinstance(plan.get('state_updates'),dict): plan['state_updates']={}
        return plan

    def _planner(self,message,history,state,ui):
        schema=json.dumps(self.tools.schemas(),separators=(',',':'))
        system='''You are Baby's planning brain for an investment research copilot. Understand natural conversation, typos, pronouns, company names and follow-ups. Decide whether tools are required. Fresh/current/today/recent/company-specific factual questions MUST use tools. General greetings/chitchat and timeless education can answer without tools. Never guess a current fact. Never request or call any order/broker execution tool. Never alter Baby scores/risk/trade plans. Return JSON only: {"intent":"...","entities":{"symbol_or_company":"..."},"needs_tools":true/false,"tool_calls":[{"name":"...","args":{}}],"response_mode":"GENERAL|EDUCATION|MARKET_QUOTE|MARKET_UPDATE|COMPANY_RESEARCH|BABY_EVIDENCE|SCREENER","state_updates":{}}. Use at most 5 tool calls. For broad recent market updates use get_market_context + get_market_news. For company news use get_company_news and usually get_quote. For a current price use get_quote. For Baby's own analysis use get_baby_research. For entry, stop/invalidation, targets, exit levels, or a complete investment analysis use get_full_investment_flow; never invent these levels. Use get_trade_plan when the user specifically asks about Baby's trade plan. A phrase like "how about Tesla stock" after a quote means Tesla/TSLA and usually requests the same quote intent. Explicit new entities override stale UI context.'''
        user={'message':message,'recent_turns':history[-6:],'conversation_state':state,'ui_context':ui,'tools':json.loads(schema)}
        return self._validate_plan(self._json(self._chat([{'role':'system','content':system},{'role':'user','content':json.dumps(user)}],650,0)))
    def _synthesize(self,message,plan,results,history,state):
        system='''You are Baby, a capable conversational investment research assistant. Answer naturally and directly. Tool results are the factual authority for current/company facts. Do not invent facts not present in tool evidence. If evidence is missing, say it is unknown/not found. Distinguish IEX from consolidated SIP. News summaries must identify source and time when available and must not claim a news item caused a price move unless evidence establishes that; say "may be relevant" or "possible catalyst" when appropriate. Baby deterministic research scores/risk/trade levels are authoritative when present; you may explain them but never change them. Entry, invalidation, targets and exit-policy values must come from Baby tool evidence, never your own calculation or prediction. Do not give a buy/sell verdict or execute/propose orders from chat. AI scoring authority 0%; chat execution authority NONE. For greetings and ordinary conversation, respond normally rather than giving a glossary fallback. Keep answers concise unless the user asks for depth.'''
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
