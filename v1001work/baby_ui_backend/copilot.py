from __future__ import annotations
import json, os, re, threading, time, urllib.request
from pathlib import Path
from .research_knowledge import STAGE_KNOWLEDGE, STATUS_LEGEND, ABBREVIATIONS, stage_explanation
from .alpaca_market import AlpacaMarketScreener
from .agentic_copilot import BabyAgenticCopilot

TOPICS = {
    'RSI': {
        'aliases':['rsi','relative strength index'],
        'brief':'RSI (Relative Strength Index) is a momentum indicator that compares recent gains with recent losses on a 0–100 scale. Common reference zones are above 70 (strong/possibly overbought momentum) and below 30 (weak/possibly oversold momentum), but those are context signals, not automatic sell/buy rules. Baby uses RSI as one technical input alongside trend, volatility, fundamentals, valuation and risk.',
        'more':'RSI is most useful for understanding momentum, not predicting a reversal by itself. Rising RSI means recent upward moves are becoming stronger relative to downward moves; falling RSI means the opposite. In a strong uptrend RSI can stay elevated for a long time, so an RSI above 70 is not automatically a sell signal. Baby combines RSI with price trend, moving averages, volatility, volume, valuation, fundamentals and Unified Risk before forming a research state.',
        'calculation':'For RSI14, Baby uses 14 periods: compute price changes, separate gains and losses, smooth their averages, calculate RS = average gain / average loss, then RSI = 100 - 100/(1 + RS). Baby calculates stock-specific RSI from the actual historical bars rather than asking an LLM to do the arithmetic.',
        'interpretation':'RSI is usually read as momentum context: below 30 is commonly called oversold, 30–70 is a broad middle range, and above 70 is commonly called overbought. Strong trends can remain above 70 or below 30 for extended periods, so Baby never treats those thresholds as standalone trading instructions.',
        'importance':'RSI helps Baby distinguish momentum strength from price level. It can support or conflict with other technical evidence, but it never overrides fundamentals, valuation, evidence quality or hard-risk constraints.',
        'example':'Example: if a stock has had many strong up days and only small down days during the last 14 periods, average gains will dominate average losses and RSI will rise. If losses dominate, RSI falls. Baby computes the exact value from price history.'
    },
    'ATR': {
        'aliases':['atr','average true range'],
        'brief':'ATR (Average True Range) measures price volatility, not direction. A larger ATR means the stock has recently moved through wider daily ranges. Baby uses ATR when constructing deterministic invalidation distances, targets and risk sizing.',
        'more':'ATR answers “how much has this stock been moving?” rather than “which direction will it move?” Baby uses that movement scale so stops and research targets are not chosen as arbitrary fixed dollar distances.',
        'calculation':'True Range is the largest of: high-low, |high-previous close|, and |low-previous close|. ATR14 smooths True Range over 14 periods.',
        'interpretation':'ATR should be interpreted relative to the stock price and its own history. High ATR means wider movement/risk; it does not by itself mean bullish or bearish.',
        'importance':'ATR is important for risk-aware trade structure because the same $2 move can be huge for one stock and normal noise for another.',
        'example':'Example: a $100 stock with ATR $2 has recently moved about two dollars per period on this volatility measure; Baby can use that scale when constructing invalidation and target distances.'
    },
    'SMA': {
        'aliases':['sma','simple moving average'],
        'brief':'SMA (Simple Moving Average) is the arithmetic average of closing prices over a chosen number of periods. Baby uses SMA20/50/200 to describe short-, medium- and long-term price structure.',
        'more':'An SMA smooths daily noise so the underlying price trend is easier to see. Longer SMAs change more slowly than shorter SMAs. Baby treats their relationship to price as technical context, not a standalone investment decision.',
        'calculation':'SMA(n) = sum of the last n closing prices divided by n.',
        'interpretation':'Price above or below an SMA provides trend context, but Baby does not use an SMA crossing alone as an investment decision.',
        'importance':'SMA structure helps Baby describe trend and potential support/resistance context while keeping the calculation fully deterministic.',
        'example':'Example: SMA20 is the average of the latest 20 closing prices. Tomorrow the oldest close leaves the window and the newest close enters it.'
    },
    'EMA': {
        'aliases':['ema','exponential moving average'],
        'brief':'EMA (Exponential Moving Average) is a moving average that gives more weight to recent prices than an SMA. Baby uses it for current trend/structure context.',
        'more':'Because recent observations receive more weight, EMA responds to price changes faster than an SMA of the same length. That makes it useful for current structure, while also making it more sensitive to short-term movement.',
        'calculation':'EMA applies a smoothing factor 2/(n+1) so newer closes receive more weight than older closes.',
        'interpretation':'EMA reacts faster than SMA. It is trend context, not a standalone buy/sell rule.',
        'importance':'EMA helps Baby measure recent trend structure and distance from trend while remaining a deterministic calculation.',
        'example':'Example: EMA20 reacts more quickly to a sudden price move than SMA20 because the latest closes have greater weight.'
    },
    'FCF': {
        'aliases':['fcf','free cash flow'],
        'brief':'FCF (Free Cash Flow) estimates cash generated by operations after capital expenditures. Baby uses it as evidence about cash generation and valuation.',
        'more':'FCF focuses on cash left after the business funds operating needs and capital investment. It can be used for debt reduction, acquisitions, buybacks, dividends or reinvestment, but one period should not be interpreted without its fiscal context.',
        'calculation':'In Baby’s financial pipeline, FCF is deterministically derived from aligned financial evidence, commonly Operating Cash Flow minus capital expenditures, with period alignment required.',
        'interpretation':'Positive and improving FCF can support financial quality, but the meaning depends on growth, capital intensity, debt, valuation and the fiscal period used.',
        'importance':'FCF helps Baby separate accounting earnings from actual cash generation and provides an input for valuation and financial-health analysis.',
        'example':'Example: if aligned operating cash flow is $10B and capital expenditures are $3B, the simple derived FCF is $7B for that same period.'
    },
    'SEC_FILINGS': {
        'aliases':['sec filing','sec filings','sec report','sec reports','10-k','10-q','8-k'],
        'brief':'SEC filings are official disclosures that public companies submit to the U.S. Securities and Exchange Commission. Baby uses supported filing evidence as a primary source for company facts and material corporate events rather than relying on an LLM to invent filing facts.',
        'more':'SEC filings give investors standardized, company-filed information. A 10-K is the annual report, a 10-Q is a quarterly report, and an 8-K reports certain material events. Registration statements such as S-1 or S-3 can describe securities that may be offered, but Baby does not treat registration language as proof that an issuance or dilution actually occurred.',
        'calculation':'SEC filings are source documents, not a calculated indicator. Baby records filing type, filing/acceptance time, period, accession and supported facts, then deterministic research components consume that evidence.',
        'interpretation':'The meaning depends on the form and the exact disclosure. Baby separates a filed disclosure from an inference: for example, a registration filing is evidence of registration, not automatically evidence that shares were issued.',
        'importance':'SEC filings are important because they are primary company disclosures for financial statements, risks, material events, financing and other information. They help Baby ground company research in auditable evidence with filing dates and provenance.',
        'example':'Example: a 10-K can provide audited annual financial statements and risk disclosures; a 10-Q provides quarterly information; an 8-K can disclose a material event. Baby should cite the exact filing evidence before making a filing-based factual claim.'
    },
    'PE': {
        'aliases':['p/e','p/e ratio','pe ratio','price earnings ratio','price-to-earnings'],
        'brief':'P/E (Price-to-Earnings ratio) compares a company’s share price with earnings per share. It is one valuation multiple, not a complete measure of whether a stock is cheap or expensive.',
        'more':'A higher P/E can reflect expectations for faster growth, stronger quality or simply a richer market price. A lower P/E can reflect cheaper valuation or weaker expected growth/risk. Baby evaluates valuation together with fundamentals and evidence quality.',
        'calculation':'P/E = share price / earnings per share for the selected earnings period. The period must be explicit because trailing and forward P/E are different measures.',
        'interpretation':'Lower is not automatically better and higher is not automatically worse. Compare the same definition across time, peers and growth/quality context.',
        'importance':'P/E provides a compact view of how much the market price represents per dollar of earnings, but Baby does not let one multiple determine the research state.',
        'example':'Example: a $100 share price divided by $5 of earnings per share gives a P/E of 20 for that earnings definition.'
    },
}

GENERIC_CONTINUATIONS = {
    'explain more','tell me more','more','go deeper','explain further','continue','keep going',
    'give me more details','give me details','can you explain more','please explain more','elaborate',
    'explain it more','tell me more about it','give me brief about it','give me a brief about it'
}

class _SessionStore:
    def __init__(self, ttl=21600): self.ttl=ttl; self._lock=threading.Lock(); self._data={}
    def get(self,sid):
        now=time.time()
        with self._lock:
            for k in list(self._data):
                if now-self._data[k].get('_ts',now)>self.ttl:self._data.pop(k,None)
            return dict(self._data.get(sid,{}) if sid else {})
    def put(self,sid,state):
        if not sid:return
        with self._lock:self._data[sid]={**state,'_ts':time.time()}

class BabyCopilot:
    def __init__(self,report_dir:Path): self.report_dir=Path(report_dir); self.market=AlpacaMarketScreener(); self.sessions=_SessionStore(); self.agentic=BabyAgenticCopilot(report_dir); self.last_agentic_fallback=None
    def _report(self,symbol):
        if not symbol:return None
        p=self.report_dir/f'{symbol.upper()}.json'
        try:return json.loads(p.read_text())
        except Exception:return None
    def _stage(self,report,stage_id): return next((x for x in (report or {}).get('stages',[]) if x.get('id')==stage_id),None)
    def _price_filter(self,text):
        pats=[r'(?:between|from)\s*\$?([0-9]+(?:\.[0-9]+)?)\s*(?:and|to|-)\s*\$?([0-9]+(?:\.[0-9]+)?)',r'\$?([0-9]+(?:\.[0-9]+)?)\s*[-–]\s*\$?([0-9]+(?:\.[0-9]+)?)']
        for p in pats:
            m=re.search(p,text,re.I)
            if m:return float(m.group(1)),float(m.group(2))
        return None
    def _topic(self,text):
        low=text.lower()
        for key,v in TOPICS.items():
            if any(re.search(rf'(?<!\w){re.escape(a)}(?!\w)',low) for a in v['aliases']):return key
        return None
    def _quote_intent(self,text):
        low=text.lower()
        freshness=any(x in low for x in ['today','right now','now','current','currently','trading at','stock price','share price','price for','price of','how much is'])
        price_words=any(x in low for x in ['price','trading at','how much','quote'])
        return bool(price_words and freshness)
    def _entity_phrase(self,text):
        # Strip quote/freshness language while preserving the company/ticker phrase.
        x=text.strip()
        patterns=[
            r'(?i)^how much is (?:the )?(?:stock |share )?price (?:for|of)\s+',
            r'(?i)^what(?:\'s| is) (?:the )?(?:stock |share )?price (?:for|of)\s+',
            r'(?i)^what is\s+', r'(?i)^how much is\s+', r'(?i)^give me\s+'
        ]
        for pat in patterns: x=re.sub(pat,'',x)
        x=re.sub(r'(?i)\b(stock|share|price|quote|trading at|today|right now|currently|current|now)\b',' ',x)
        x=re.sub(r'(?i)\b(for|of|please|the)\b',' ',x)
        return ' '.join(x.replace('?',' ').split()).strip(' .,$')
    def _explicit_symbol_reference(self,text):
        # Conservative ticker recognition for explicit all-caps symbols in user text.
        m=re.search(r'(?<![A-Za-z])\$?([A-Z]{1,5})(?![A-Za-z])',text)
        return m.group(1) if m else None
    def _current_quote(self,text,state):
        phrase=self._entity_phrase(text)
        # Follow-ups such as "what about AMD?" can provide a ticker without saying price again.
        explicit=self._explicit_symbol_reference(text)
        resolved=self.market.resolve_company(explicit or phrase)
        if not resolved or not resolved.get('symbol'):
            return None, resolved
        symbol=resolved['symbol'].upper(); q=self.market.current_quote(symbol)
        state['symbol']=symbol; state['active_symbol']=symbol; state['active_topic']=None; state['active_stage']=None; state['previous_intent']='CURRENT_STOCK_QUOTE'
        return q, resolved
    def _normalize(self,text): return re.sub(r'[^a-z0-9/$%+.-]+',' ',text.lower()).strip()
    def _normalized_words(self,text):
        words=self._normalize(text).split()
        # Conservative typo repair for conversational routing only. This never changes symbols,
        # prices, research facts or order parameters.
        repaired=[]
        for w in words:
            if w in {'howb','howw','hwo'}: w='how'
            elif w in {'whatt','waht'}: w='what'
            elif w in {'abot','abuot'}: w='about'
            repaired.append(w)
        return repaired
    def _about_followup(self,text):
        words=self._normalized_words(text)
        if 'about' not in words:return False
        i=words.index('about')
        if i==0:return True
        return words[i-1] in {'what','how'} or (i>=2 and words[i-2:i]==['what','do'])
    def _after_about(self,text):
        words=self._normalized_words(text)
        if 'about' not in words:return ''
        return ' '.join(words[words.index('about')+1:]).strip(' ?.,$')
    def _safe_education_answer(self,topic,text,kind=None):
        if topic in TOPICS:return self._topic_answer(topic,text,kind)
        if topic in STATUS_LEGEND:return STATUS_LEGEND[topic]
        if topic in ABBREVIATIONS:
            meaning=ABBREVIATIONS[topic]
            if topic=='SEC':
                return self._topic_answer('SEC_FILINGS',text,kind)
            return f'{topic} means {meaning}.'
        return None
    def _followup_kind(self,text):
        low=text.lower().strip(); norm=self._normalize(text)
        if norm in GENERIC_CONTINUATIONS:return 'MORE'
        if re.search(r'\b(it|this|that|its|they|their|this score|this indicator|that indicator|those|them)\b',low):
            if any(x in low for x in ['calculate','formula','computed','derive']):return 'CALCULATION'
            if any(x in low for x in ['good','bad','high','low','interpret','mean']):return 'INTERPRETATION'
            if any(x in low for x in ['important','matter','useful','care']):return 'IMPORTANCE'
            if 'example' in low:return 'EXAMPLE'
            return 'MORE'
        if re.search(r'\bhow\s+(?:is|was|do|does)\b.*\b(calculat|comput|deriv)',low):return 'CALCULATION'
        if any(x in low for x in ['how is it calculated','what is the formula','show the formula']):return 'CALCULATION'
        if any(x in low for x in ['what is a good value','is that good or bad','is it good or bad','what does that mean']):return 'INTERPRETATION'
        if any(x in low for x in ['why is it important','why does it matter','why is that important']):return 'IMPORTANCE'
        if any(x in low for x in ['give me an example','show me an example','example please']):return 'EXAMPLE'
        return None
    def _topic_answer(self,topic,text,kind=None):
        t=TOPICS[topic]; low=text.lower(); kind=kind or self._followup_kind(text)
        if kind=='CALCULATION' or any(x in low for x in ['calculate','calculated','formula','how do you get','how did you get']):return t['calculation']
        if kind=='INTERPRETATION' or any(x in low for x in ['good value','interpret','overbought','oversold']):return t['interpretation']
        if kind=='IMPORTANCE':return t['importance']
        if kind=='EXAMPLE':return t['example']
        if kind=='MORE':return t['more']
        return t['brief']
    def _state_public(self,s): return {k:v for k,v in s.items() if not k.startswith('_')}
    def runtime_status(self):
        requested=(os.getenv('BABY_COPILOT_MODE') or 'AUTO').strip().upper()
        provider=self.agentic.status()
        if requested=='LEGACY' or not provider.get('configured'):
            state='LEGACY'
        elif provider.get('state')=='DEGRADED' or self.last_agentic_fallback:
            state='DEGRADED'
        else:
            state='AGENTIC'
        return {'state':state,'requested_mode':requested,'provider':provider,'last_fallback':self.last_agentic_fallback,
                'fallback_available':True,'AI_SCORING_AUTHORITY':'0%','CHAT_EXECUTION_AUTHORITY':'NONE','REAL_MONEY_EXECUTION':'DISABLED'}

    def ask(self,message:str,context:dict|None=None,session_id:str|None=None)->dict:
        incoming=context or {}; text=(message or '').strip(); low=text.lower()
        if not text: raise ValueError('message is required')
        # V9.0.1 runtime policy: explicit LEGACY mode is deterministic; AUTO/AGENTIC
        # prefer the configured AI provider chain but NEVER let provider failures take down Ask Baby.
        mode=(os.getenv('BABY_COPILOT_MODE') or 'AUTO').strip().upper()
        if mode not in {'AUTO','AGENTIC','LEGACY'}: mode='AUTO'
        if mode != 'LEGACY' and self.agentic.available():
            try:
                result=self.agentic.ask(text,incoming,session_id)
                self.last_agentic_fallback=None
                result['runtime']={'state':'AGENTIC','fallback':False,'provider':self.agentic.status().get('last_provider') or self.agentic.status().get('active_provider')}
                return result
            except Exception as e:
                self.last_agentic_fallback={'error_type':type(e).__name__,'error':str(e)[:500],'at':time.time(),'message_preview':text[:120]}
                # Continue into the proven deterministic V8.7.4 path. This is deliberate
                # degradation, not an HTTP 500/503. Current facts still come from tools.
        # If configured but circuit-open/provider-failed, deterministic routing remains usable.
        state=self.sessions.get(session_id)
        for k in ('symbol','stage_id','stage_label','page'):
            if incoming.get(k) not in (None,''):state[k]=incoming[k]
        # Highest priority: an explicit fresh quote request overrides old UI/topic context.
        if self._quote_intent(text):
            q,resolved=self._current_quote(text,state)
            if q and q.get('price') is not None:
                self.sessions.put(session_id,state)
                ch=q.get('change'); pct=q.get('change_pct'); movement=''
                if ch is not None and pct is not None: movement=f" ({ch:+.2f}, {pct:+.2f}% vs previous close)"
                answer=f"{q['symbol']} is ${q['price']:.2f}{movement}. Source: Alpaca Market Data · {q.get('feed','UNKNOWN')}. Quote timestamp: {q.get('timestamp') or 'UNKNOWN'}."
                if q.get('feed')=='IEX': answer+=' IEX is not the full consolidated SIP feed, so prices can differ slightly from another broker/feed.'
                return {'mode':'MARKET_QUOTE','answer':answer,'data':q,'evidence':[{'label':f"Alpaca Market Data · {q.get('feed','UNKNOWN')}",'kind':'MARKET'}],'context_state':self._state_public(state)}
            if resolved and resolved.get('resolution')=='AMBIGUOUS':
                self.sessions.put(session_id,state)
                return {'mode':'MARKET_QUOTE','answer':'I found multiple matching companies. Please use the ticker or a more specific company name.','data':resolved,'context_state':self._state_public(state)}
            self.sessions.put(session_id,state)
            return {'mode':'MARKET_QUOTE','answer':'I could not resolve that company/ticker to an active Alpaca US-equity asset. Please give me the ticker symbol.','data':resolved or {},'context_state':self._state_public(state)}

        symbol=str(state.get('symbol') or '').upper(); stage_id=state.get('stage_id')
        explicit_topic=self._topic(text); followup=self._followup_kind(text); topic=explicit_topic
        if state.get('previous_intent')=='CURRENT_STOCK_QUOTE' and (self._about_followup(text) or re.search(r'(?i)^\s*and\b',text)):
            explicit=self._explicit_symbol_reference(text)
            phrase=self._after_about(text) if self._about_followup(text) else re.sub(r'(?i)^\s*and\b','',text).strip(' ?')
            phrase=re.sub(r'(?i)\b(stock|share|price|quote|today|now|please)\b',' ',phrase)
            phrase=' '.join(phrase.split())
            resolved=self.market.resolve_company(explicit or phrase)
            if resolved and resolved.get('symbol'):
                q=self.market.current_quote(resolved['symbol']); state['symbol']=resolved['symbol']; state['active_symbol']=resolved['symbol']; state['active_topic']=None; state['active_stage']=None; state['previous_intent']='CURRENT_STOCK_QUOTE'; self.sessions.put(session_id,state)
                ch=q.get('change'); pct=q.get('change_pct'); movement=f" ({ch:+.2f}, {pct:+.2f}% vs previous close)" if ch is not None and pct is not None else ''
                return {'mode':'MARKET_QUOTE','answer':f"{q['symbol']} is ${q['price']:.2f}{movement}. Source: Alpaca Market Data · {q.get('feed','UNKNOWN')}. Quote timestamp: {q.get('timestamp') or 'UNKNOWN'}.",'data':q,'evidence':[{'label':f"Alpaca Market Data · {q.get('feed','UNKNOWN')}",'kind':'MARKET'}],'context_state':self._state_public(state)}
        if explicit_topic:
            state['active_topic']=explicit_topic; state['active_stage']=None
        elif followup and state.get('active_topic'):
            # Explicit deictic score/stage language targets the visible UI stage; generic continuation stays on the active topic.
            stage_deictic = bool(stage_id and (re.search(r'\b(this|that)\b', low) and any(x in low for x in ['score','low','high','stage','status','valuation','risk','why'])))
            if not stage_deictic:
                topic='SEC_FILINGS' if state['active_topic']=='SEC' else state['active_topic']

        pr=self._price_filter(text)
        if pr and any(w in low for w in ['stock','stocks','show','find','filter','between','from']):
            state['active_filter']={'type':'PRICE_RANGE','min_price':pr[0],'max_price':pr[1]}; state['previous_intent']='TOOL_ACTION'
            data=self.market.filter_price(*pr,limit=int(incoming.get('limit') or 100)); self.sessions.put(session_id,state)
            return {'mode':'TOOL_ACTION','answer':f"Found {data['count']} active/tradable US equities in the ${pr[0]:g}–${pr[1]:g} range using Alpaca IEX market data. Showing up to {len(data['results'])}.",'data':data,'evidence':[{'label':'Alpaca Market Data · IEX','kind':'MARKET'}],'context_state':self._state_public(state)}
        if state.get('active_filter') and followup and any(w in low for w in ['show','stocks','them','those','again']):
            f=state['active_filter']; data=self.market.filter_price(f['min_price'],f['max_price'],limit=int(incoming.get('limit') or 100)); self.sessions.put(session_id,state)
            return {'mode':'TOOL_ACTION','answer':f"Keeping your active price filter: ${f['min_price']:g}–${f['max_price']:g}. Found {data['count']} matching active/tradable equities.",'data':data,'evidence':[{'label':'Alpaca Market Data · IEX','kind':'MARKET'}],'context_state':self._state_public(state)}

        if topic:
            state['previous_intent']='EDUCATION'; state['active_topic']=topic; self.sessions.put(session_id,state)
            return {'mode':'EDUCATION','answer':self._safe_education_answer(topic,text,followup) or 'I do not have a deterministic explanation for that topic yet.','data':{'topic':topic,'followup_kind':followup},'context_state':self._state_public(state)}
        for k,v in STATUS_LEGEND.items():
            if low in {k.lower(),f'what is {k.lower()}',f'what does {k.lower()} mean'}:
                state['active_topic']=k; state['previous_intent']='EDUCATION'; self.sessions.put(session_id,state); return {'mode':'EDUCATION','answer':v,'data':{'status':k},'context_state':self._state_public(state)}
        for k,v in ABBREVIATIONS.items():
            if re.search(rf'\b{re.escape(k.lower())}\b',low) and any(x in low for x in ['what','mean','explain']):
                canonical='SEC_FILINGS' if k=='SEC' else k; state['active_topic']=canonical; state['previous_intent']='EDUCATION'; self.sessions.put(session_id,state); answer=self._safe_education_answer(canonical,text) or f'{k} means {v}.'; return {'mode':'EDUCATION','answer':answer,'data':{'abbreviation':k,'meaning':v,'topic':canonical},'context_state':self._state_public(state)}

        report=self._report(symbol)
        # UI-stage deictic follow-up applies when no active conversational topic captured the turn.
        if stage_id and stage_id in STAGE_KNOWLEDGE and not (stage_id=='decision' and any(x in low for x in ['watch','candidate','score','status','risk','research'])) and (followup or any(x in low for x in ['what','explain','mean','why','how'])):
            st=self._stage(report,stage_id); ex=stage_explanation(stage_id,st); cur=ex.get('current') or {}
            answer=f"{STAGE_KNOWLEDGE[stage_id]['what']} {STAGE_KNOWLEDGE[stage_id]['why']}"
            if symbol and cur:
                answer+=f" For {symbol}, this stage is {cur.get('status') or 'UNKNOWN'}"+(f" with score {cur.get('score'):.1f}/100." if isinstance(cur.get('score'),(int,float)) else '.')
                reasons=(cur.get('negatives') or [])+(cur.get('conflicts') or [])+(cur.get('unknowns') or [])
                if ('why' in low or followup=='MORE') and reasons:answer+=' Current exported reasons include: '+'; '.join(map(str,reasons[:4]))+'.'
            answer+=' '+STAGE_KNOWLEDGE[stage_id]['result']; state['previous_intent']='EVIDENCE_QA'; state['active_stage']=stage_id; self.sessions.put(session_id,state)
            return {'mode':'EVIDENCE_QA' if report else 'EDUCATION','answer':answer,'data':ex,'evidence':[{'label':f'{symbol} · {stage_id}' if symbol else stage_id,'kind':'BABY_RESEARCH'}],'context_state':self._state_public(state)}
        if report and symbol and any(x in low for x in ['why','status','score','watch','candidate','research','risk','valuation','trade']):
            tp=report.get('trade_plan') or {}; setup=(tp.get('current_setup') or {})
            answer=(f"{symbol} is currently {report.get('decision','UNKNOWN')} with research score {report.get('score','UNKNOWN')}/100, confidence {report.get('confidence','UNKNOWN')}% and evidence coverage {report.get('coverage','UNKNOWN')}%. Unified Risk is {report.get('risk','UNKNOWN')}. Current trade setup: {setup.get('status') or tp.get('status') or 'NOT_PRODUCED'}.")
            val=self._stage(report,'valuation')
            if val and val.get('score') is not None:answer+=f" Valuation score is {val['score']}/100."
            if setup.get('reason'):answer+=' '+setup['reason']
            state['previous_intent']='EVIDENCE_QA'; self.sessions.put(session_id,state)
            return {'mode':'EVIDENCE_QA','answer':answer,'data':{'symbol':symbol,'decision':report.get('decision'),'score':report.get('score'),'confidence':report.get('confidence'),'coverage':report.get('coverage'),'risk':report.get('risk'),'trade_setup':setup},'evidence':[{'label':f'{symbol} production research','kind':'BABY_RESEARCH'}],'context_state':self._state_public(state)}
        llm=self._nemotron(text,{**state,**incoming})
        if llm:
            state['previous_intent']='EDUCATION'; self.sessions.put(session_id,state); return {'mode':'EDUCATION','answer':llm,'data':{},'evidence':[{'label':'Nemotron · explanation only','kind':'AI_EXPLANATION'}],'context_state':self._state_public(state)}
        self.sessions.put(session_id,state)
        return {'mode':'EDUCATION','answer':'I can explain a Research Pipeline stage, answer from the current Baby evidence, or run deterministic stock filters. Try “What is RSI?”, “Why is this score low?”, or “show stocks between $10 and $20.”','data':{'examples':['What is RSI?','Why is this score low?','How is it calculated?','Show stocks between $10 and $20']},'context_state':self._state_public(state)}
    def _nemotron(self,text,context):
        key=os.getenv('NVIDIA_API_KEY')
        if not key:return None
        active=context.get('active_topic'); topic_context=f" Active educational topic: {active}. Treat generic follow-ups as continuing that topic." if active else ''
        payload={'model':'nvidia/nemotron-3-ultra-550b-a55b','messages':[{'role':'system','content':'You are Baby Research Copilot. Give concise educational explanations of investing terminology. Do not invent current market/company facts, scores, prices, recommendations, or orders. Never execute or propose an order from chat. If current Baby evidence is required, say to use Baby research tools.'+topic_context},{'role':'user','content':text}],'temperature':0.2,'max_tokens':450}
        req=urllib.request.Request('https://integrate.api.nvidia.com/v1/chat/completions',data=json.dumps(payload).encode(),headers={'Authorization':f'Bearer {key}','Content-Type':'application/json'})
        try:
            with urllib.request.urlopen(req,timeout=45) as r:d=json.loads(r.read().decode())
            return d['choices'][0]['message']['content'].strip()
        except Exception:return None
