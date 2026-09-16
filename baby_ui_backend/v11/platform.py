from __future__ import annotations
import hashlib, json, math, sqlite3
from datetime import datetime, timezone
from pathlib import Path

ACTIVE={'AT_PULLBACK_ZONE','BREAKOUT_TRIGGERED'}
STRENGTH={'LOW':1.0,'MEDIUM':2.0,'HIGH':3.0,'CRITICAL':4.0}


def now(): return datetime.now(timezone.utc).isoformat()
def num(v):
    try:
        x=float(v); return x if math.isfinite(x) else None
    except Exception:return None
def up(v,d='UNKNOWN'): return str(v if v not in (None,'') else d).upper()
def clamp(x,a=0,b=100): return max(a,min(b,float(x)))
def stage_map(v106): return {s.get('id'):s for s in (v106.get('stages') or []) if isinstance(s,dict)}
def metric_map(stage): return {m.get('key'):m for m in (stage.get('metrics') or []) if isinstance(m,dict)}
def val(ms,k): return num((ms.get(k) or {}).get('value'))
def first_val(ms,*keys):
    for k in keys:
        x=val(ms,k)
        if x is not None:return x
    return None

def evidence_id(symbol,stage,key,metric):
    raw='|'.join(map(str,[symbol,stage,key,metric.get('status'),metric.get('value'),json.dumps(metric.get('inputs') or {},sort_keys=True,default=str)]))
    return hashlib.sha256(raw.encode()).hexdigest()[:20]

class EvidenceGraph:
    def build(self,symbol,v106):
        nodes=[]; edges=[]; contradictions=[]; stale=[]; unknown=[]; applicable=0; decision_grade=0
        stages=v106.get('stages') or []
        for s in stages:
            if up(s.get('status'))=='NOT_APPLICABLE': continue
            sid=s.get('id','unknown')
            for m in s.get('metrics') or []:
                if not isinstance(m,dict): continue
                key=m.get('key','unknown'); eid=evidence_id(symbol,sid,key,m); status=up(m.get('status'))
                node={'id':eid,'stage':sid,'key':key,'value':m.get('value'),'status':status,'inputs':m.get('inputs') or {},'provenance':m.get('provenance') or [],'authority':m.get('authority') or 'BABY_DETERMINISTIC','as_of':m.get('as_of')}
                nodes.append(node); applicable+=1
                if status in {'UNKNOWN','NOT_AVAILABLE','INVALID_PERIOD_ALIGNMENT'}: unknown.append(eid)
                elif status not in {'STALE','FAIL','BLOCKED'}: decision_grade+=1
                if status=='STALE': stale.append(eid)
                for dep in (m.get('dependencies') or []): edges.append({'from':str(dep),'to':eid,'relation':'DERIVES'})
        sm=stage_map(v106); tech=metric_map(sm.get('technical_v102',{})); fund=metric_map(sm.get('fundamentals_v101',{}))
        trend=up((tech.get('trend_regime') or {}).get('value')); ni=val(fund,'net_income')
        if trend=='BULLISH' and ni is not None and ni<0:
            contradictions.append({'type':'CROSS_DOMAIN_TENSION','left':'BULLISH_TECHNICAL','right':'NEGATIVE_NET_INCOME','severity':'HIGH','materiality':3})
        pipeline_total=len(stages); pipeline_done=sum(1 for s in stages if up(s.get('status')) not in {'UNKNOWN','NOT_AVAILABLE'})
        evidence_cov=round(100*(applicable-len(unknown))/applicable,2) if applicable else 0
        applicable_stages=[s for s in stages if up(s.get('status'))!='NOT_APPLICABLE']
        stage_covs=[num(s.get('coverage')) or 0 for s in applicable_stages]
        stage_coverage=sum(stage_covs)/len(stage_covs) if stage_covs else 0
        metric_grade=100*decision_grade/applicable if applicable else 0
        # Decision-grade coverage is constrained by both metric validity and domain/stage coverage.
        # An empty UNKNOWN domain therefore cannot masquerade as 100% coverage.
        dg_cov=round(min(metric_grade,stage_coverage),2)
        return {'symbol':symbol,'nodes':nodes,'edges':edges,'unknown_evidence_ids':unknown,'stale_evidence_ids':stale,'contradictions':contradictions,
                'pipeline_coverage':round(100*pipeline_done/pipeline_total,2) if pipeline_total else 0,'evidence_coverage':evidence_cov,'decision_grade_coverage':dg_cov,
                'coverage':evidence_cov,'generated_at':now()}

class ThesisEngine:
    def _item(self,kind,text,evidence=None,strength='MEDIUM',materiality=None):
        materiality=materiality if materiality is not None else STRENGTH.get(strength,2)
        return {'kind':kind,'text':text,'strength':strength,'materiality':materiality,'weight':STRENGTH.get(strength,2)*materiality,'evidence':evidence or []}
    def build(self,symbol,v106,research,graph):
        sm=stage_map(v106); fstage=sm.get('fundamentals_v101',{}); f=metric_map(fstage); t=metric_map(sm.get('technical_v102',{})); va=metric_map(sm.get('valuation_v105',{}))
        asset_type=up(v106.get('asset_type') or v106.get('profile',{}).get('asset_type') or ('ETF' if up(fstage.get('status'))=='NOT_APPLICABLE' else 'OPERATING_COMPANY'))
        bull=[]; bear=[]; unknown=[]; catalysts=[]
        trend=up((t.get('trend_regime') or {}).get('value')); rsi=val(t,'rsi14'); rvol=val(t,'rvol')
        if asset_type!='ETF':
            rg=first_val(f,'revenue_growth_yoy','revenue_growth'); nm=val(f,'net_margin'); fcf=val(f,'fcf'); cash=val(f,'cash'); debt=val(f,'debt')
            if rg is not None: (bull if rg>10 else bear if rg<0 else bull).append(self._item('GROWTH',f'Revenue growth is {rg:.1f}%.',strength='HIGH' if abs(rg)>=20 else 'MEDIUM',materiality=3))
            else: unknown.append('Revenue growth is unavailable.')
            if nm is not None: (bull if nm>10 else bear if nm<0 else bull).append(self._item('PROFITABILITY',f'Net margin is {nm:.1f}%.',materiality=3))
            if fcf is not None: (bull if fcf>0 else bear).append(self._item('CASH_FLOW',f'Free cash flow is {fcf:,.0f}.',strength='HIGH',materiality=4))
            else: unknown.append('Aligned free cash flow is unavailable.')
            if cash is not None and debt is not None: (bull if cash>=debt else bear).append(self._item('BALANCE_SHEET',f'Cash/debt relationship is {cash:,.0f}/{debt:,.0f}.',materiality=3))
        else:
            unknown.append('Operating-company fundamentals are not applicable to ETF assets.')
        if trend=='BULLISH': bull.append(self._item('MARKET','Technical trend regime is BULLISH.',materiality=3))
        elif trend=='BEARISH': bear.append(self._item('MARKET','Technical trend regime is BEARISH.',materiality=3))
        if rsi is not None and rsi>=70: bear.append(self._item('MOMENTUM',f'RSI14 is {rsi:.1f}, an extended momentum condition.',materiality=2))
        elif rsi is not None and 50<=rsi<70: bull.append(self._item('MOMENTUM',f'RSI14 is {rsi:.1f}, showing positive momentum without the deterministic overbought flag.',materiality=2))
        if rvol is not None and rvol>=1.5: bull.append(self._item('VOLUME',f'Relative volume is expanded at {rvol:.2f}x.',strength='LOW',materiality=1))
        if asset_type!='ETF':
            pe=val(va,'pe_ttm'); fy=val(va,'fcf_yield_ttm'); rd=val(va,'reverse_dcf_growth')
            if pe is not None and pe>60: bear.append(self._item('VALUATION',f'P/E basis is elevated at {pe:.1f}x.',strength='HIGH' if pe>100 else 'MEDIUM',materiality=4))
            if fy is not None: (bull if fy>=4 else bear if fy<2 else bull).append(self._item('VALUATION',f'FCF yield is {fy:.2f}%.',materiality=3))
            if rd is not None and rd>30: bear.append(self._item('EXPECTATIONS',f'Reverse-DCF scenario requires approximately {rd:.1f}% growth under the configured assumptions.',strength='HIGH',materiality=4))
        events=sm.get('events_v103',{}); ec=events.get('event_count')
        if ec: catalysts.append({'type':'NEWS_EVENT_SET','count':ec,'causality':'NOT_ESTABLISHED','status':'REVIEW_REQUIRED'})
        risk=up(research.get('risk')); hard=bool(research.get('hard_risk_override'))
        if hard or risk in {'VERY_HIGH','EXTREME'}: bear.append(self._item('RISK',f'Unified risk is {risk}; hard override={hard}.',strength='CRITICAL' if hard else 'HIGH',materiality=5))
        if asset_type=='ETF' and not bull and not bear: unknown.append('ETF thesis has insufficient market/regime evidence for directional classification.')
        bull_weight=round(sum(x['weight'] for x in bull),2); bear_weight=round(sum(x['weight'] for x in bear),2)
        return {'symbol':symbol,'asset_type':asset_type,'bull_case':bull,'bear_case':bear,'bull_weight':bull_weight,'bear_weight':bear_weight,'net_evidence_weight':round(bull_weight-bear_weight,2),
                'unknowns':unknown,'contradictions':graph.get('contradictions') or [],'catalysts':catalysts,'risk_level':risk,'hard_risk_override':hard,'authority':'BABY_DETERMINISTIC','ai_authority':'NONE'}

class ExpectationsEngine:
    def build(self,v106):
        sm=stage_map(v106); fstage=sm.get('fundamentals_v101',{}); va=metric_map(sm.get('valuation_v105',{})); f=metric_map(fstage)
        if up(fstage.get('status'))=='NOT_APPLICABLE':
            return {'status':'NOT_APPLICABLE','reverse_dcf_required_growth':None,'observed_revenue_growth':None,'observed_net_income_growth':None,'observed_ocf_growth':None,'observed_fcf_growth':None,'expectation_gap_pct_points':None,'interpretation':'Operating-company growth expectations are not applicable to this asset type.','authority':'DETERMINISTIC'}
        rd=val(va,'reverse_dcf_growth'); rg=first_val(f,'revenue_growth_yoy','revenue_growth'); ng=first_val(f,'net_income_growth_yoy','net_income_growth'); og=first_val(f,'ocf_growth_yoy','ocf_growth'); fg=val(f,'fcf_growth_yoy')
        observed=rg if rg is not None else fg if fg is not None else og
        gap=None; status='UNKNOWN'; pressure='UNKNOWN'
        if rd is not None and observed is not None:
            gap=round(rd-observed,2); status='DEMANDING' if gap>15 else 'BALANCED' if gap>=-10 else 'CONSERVATIVE'; pressure='HIGH' if gap>25 else 'MODERATE' if gap>10 else 'LOW'
        return {'status':status,'reverse_dcf_required_growth':rd,'observed_revenue_growth':rg,'observed_net_income_growth':ng,'observed_ocf_growth':og,'observed_fcf_growth':fg,'observed_growth_basis':'REVENUE_YOY' if rg is not None else 'FCF_YOY' if fg is not None else 'OCF_YOY' if og is not None else None,
                'expectation_gap_pct_points':gap,'expectations_pressure':pressure,'interpretation':'Scenario comparison only; reverse DCF is not an objective fair value.','authority':'DETERMINISTIC'}

class DecisionV2:
    WEIGHTS={'fundamentals_v101':.24,'technical_v102':.18,'events_v103':.08,'macro_v104':.10,'valuation_v105':.20,'institutional_v106':.05}
    def build(self,v106,research,thesis,expect,graph):
        sm=stage_map(v106); parts={}; weighted=den=0
        for sid,w in self.WEIGHTS.items():
            s=sm.get(sid,{}); status=up(s.get('status')); cov=num(s.get('coverage')) or 0; score=num(s.get('score'))
            if status=='NOT_APPLICABLE': parts[sid]={'score':None,'coverage':0,'weight':w,'status':'NOT_APPLICABLE'}; continue
            if score is None:
                vals=[num(m.get('score')) for m in metric_map(s).values()]; vals=[x for x in vals if x is not None]; score=sum(vals)/len(vals) if vals else None
            if score is not None and cov>0: weighted+=score*w; den+=w; parts[sid]={'score':round(score,2),'coverage':cov,'weight':w}
            else: parts[sid]={'score':None,'coverage':cov,'weight':w,'status':'OMITTED_NOT_BEARISH'}
        base=weighted/den if den else num(research.get('score')) or 50; prod=num(research.get('score')); base=(.70*prod+.30*base) if prod is not None else base
        # Weighted evidence is capped so one severe item can outweigh several weak observations without overwhelming production scoring.
        net=thesis.get('net_evidence_weight',0); evidence_adjust=clamp(net/6,-8,8); contradiction_penalty=sum({'LOW':.5,'MEDIUM':1,'REVIEW':1.5,'HIGH':3,'CRITICAL':5}.get(up(c.get('severity')),1) for c in thesis.get('contradictions',[]))
        score=clamp(base+evidence_adjust-contradiction_penalty)
        hard=bool(research.get('hard_risk_override')); risk=up(research.get('risk')); constraints=[]
        if hard or risk in {'VERY_HIGH','EXTREME'}: score=min(score,44); constraints.append('HARD_RISK_OR_VERY_HIGH_RISK_CAP')
        pipeline_cov=num(graph.get('pipeline_coverage')) or 0; evidence_cov=num(graph.get('evidence_coverage')) or 0; decision_cov=num(graph.get('decision_grade_coverage')) or 0
        source_conf=num(research.get('confidence')) or 0; conf=round(min(source_conf,decision_cov) if source_conf else decision_cov,2)
        if decision_cov<60 or conf<45: constraints.append('LOW_DECISION_GRADE_EVIDENCE')
        state='TOP_RESEARCH' if score>=75 else 'CANDIDATE' if score>=62 else 'WATCH' if score>=48 else 'WAIT' if score>=35 else 'AVOID'
        if hard and state in {'TOP_RESEARCH','CANDIDATE','WATCH'}: state='WAIT'
        return {'score':round(score,2),'state':state,'confidence':conf,'coverage':round(decision_cov,2),'pipeline_coverage':round(pipeline_cov,2),'evidence_coverage':round(evidence_cov,2),'decision_grade_coverage':round(decision_cov,2),
                'evidence_adjustment':round(evidence_adjust,2),'contradiction_penalty':round(contradiction_penalty,2),'components':parts,'constraints':constraints,'production_v10_decision':research.get('decision'),'production_v10_score':prod,'authority':'BABY_DETERMINISTIC_V11_0_1','ai_scoring_authority':'0%','meaning':'Research attractiveness, not a prediction or buy/sell instruction.'}

class ThesisState:
    def build(self,current,previous):
        if not previous:return {'state':'BASELINE','score_change':None,'changed_evidence':[]}
        c=num(current.get('decision',{}).get('score')); p=num(previous.get('decision',{}).get('score')); delta=(c-p) if c is not None and p is not None else None
        state='STABLE' if delta is None or abs(delta)<3 else 'STRENGTHENING' if delta>0 else 'WEAKENING'
        if current.get('thesis',{}).get('hard_risk_override'): state='BROKEN_OR_CONSTRAINED'
        old={n['id'] for n in previous.get('evidence_graph',{}).get('nodes',[]) if isinstance(n,dict)}; new={n['id'] for n in current.get('evidence_graph',{}).get('nodes',[]) if isinstance(n,dict)}
        return {'state':state,'score_change':round(delta,2) if delta is not None else None,'changed_evidence':sorted(new.symmetric_difference(old))[:50]}

class PortfolioIntelligence:
    def build(self,portfolio,flow):
        p=portfolio or {}; account=p.get('account') or {}; positions=p.get('positions') or []; equity=num(account.get('equity')); symbol=flow.get('symbol'); existing=next((x for x in positions if up(x.get('symbol'))==symbol),None)
        return {'equity':equity,'cash':num(account.get('cash')),'existing_symbol_position':existing,'position_count':len(positions),'concentration_status':'REVIEW_REQUIRED' if existing else 'NO_EXISTING_SYMBOL_POSITION','correlation_status':'UNKNOWN_WITHOUT_RETURN_MATRIX','sector_exposure_status':'UNKNOWN_WITHOUT_POSITION_CLASSIFICATION','authority':'DETERMINISTIC','note':'V11 does not invent correlation or sector exposure when portfolio evidence is absent.'}

class DecisionJournal:
    def __init__(self,path='data/baby_v11_journal.db'): self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True); self._init()
    def _init(self):
        with sqlite3.connect(self.path) as c:c.execute('CREATE TABLE IF NOT EXISTS decisions(id INTEGER PRIMARY KEY AUTOINCREMENT,symbol TEXT,created_at TEXT,version TEXT,score REAL,state TEXT,payload TEXT,artifact_hash TEXT)')
    def latest(self,symbol):
        with sqlite3.connect(self.path) as c:r=c.execute('SELECT payload FROM decisions WHERE symbol=? ORDER BY id DESC LIMIT 1',(symbol,)).fetchone()
        return json.loads(r[0]) if r else None
    def record(self,symbol,payload):
        raw=json.dumps(payload,sort_keys=True,default=str); h=hashlib.sha256(raw.encode()).hexdigest()
        with sqlite3.connect(self.path) as c:c.execute('INSERT INTO decisions(symbol,created_at,version,score,state,payload,artifact_hash) VALUES(?,?,?,?,?,?,?)',(symbol,now(),'11.0.1',num(payload.get('decision',{}).get('score')),payload.get('decision',{}).get('state'),raw,h))
        return {'recorded':True,'artifact_hash':h,'database':str(self.path)}

class V11InvestmentPlatform:
    def __init__(self,journal_path='data/baby_v11_journal.db'):
        self.graph=EvidenceGraph(); self.thesis=ThesisEngine(); self.expect=ExpectationsEngine(); self.decider=DecisionV2(); self.state=ThesisState(); self.portfolio=PortfolioIntelligence(); self.journal=DecisionJournal(journal_path)
    def build(self,symbol,research,v106,flow,*,record=False):
        symbol=symbol.upper(); graph=self.graph.build(symbol,v106); thesis=self.thesis.build(symbol,v106,research,graph); exp=self.expect.build(v106); decision=self.decider.build(v106,research,thesis,exp,graph)
        trade=flow.get('trade_plan') or {}; proposal=flow.get('paper_proposal') or {}; current=flow.get('current_setup') or {}; exitp=flow.get('exit_policy') or {}
        trade_intel={'setup_status':current.get('status') or trade.get('status'),'entry_triggered':up(current.get('status') or trade.get('status')) in ACTIVE,'pullback':trade.get('pullback'),'breakout':trade.get('breakout'),'position':trade.get('position'),'exit_policy':exitp,'paper_proposal':proposal,'paper_execution_requires_explicit_confirmation':True,'real_money':'DISABLED','authority':'BABY_DETERMINISTIC'}
        portfolio=self.portfolio.build(flow.get('portfolio'),flow)
        shell={'symbol':symbol,'schema_version':'11.0.1','generated_at':now(),'evidence_graph':graph,'thesis':thesis,'expectations':exp,'decision':decision,'trade_intelligence':trade_intel,'portfolio_intelligence':portfolio}
        prev=self.journal.latest(symbol); shell['thesis_state']=self.state.build(shell,prev)
        shell['validation']={'status':'PASS' if not graph.get('stale_evidence_ids') else 'REVIEW','unsupported_claim_policy':'BLOCK','missing_evidence_policy':'UNKNOWN_NOT_BEARISH','lookahead_policy':'POINT_IN_TIME_REQUIRED_FOR_HISTORICAL_USE','oos_validation':'HOOK_AVAILABLE_NOT_RUN_IN_LIVE_REPORT','benchmark_validation':'USE_EXISTING_V7/V7.5 HISTORICAL_PLATFORM','ai_score_authority':'0%','ai_execution_authority':'NONE'}
        shell['analyst_context']={'executive_thesis':self.summary(shell),'questions_supported':['Why this decision?','What worries you?','What supports the thesis?','What would invalidate it?','Why this entry?','What is unknown?'],'rule':'LLM may explain this structure but may not change facts, score, risk, trade levels, or execution state.'}
        shell['authority']={'FACTS':'VERIFIED_SOURCE_EVIDENCE','CALCULATIONS':'BABY_DETERMINISTIC','DECISION':'BABY_V11_DECISION_ENGINE','TRADE_LEVELS':'EXISTING_BABY_TRADE_PLAN_AGENT','LLM_FACT_AUTHORITY':'NONE','LLM_SCORING_AUTHORITY':'0%','LLM_RISK_OVERRIDE_AUTHORITY':'0%','LLM_EXECUTION_AUTHORITY':'NONE','REAL_MONEY':'DISABLED'}
        if record:shell['journal']=self.journal.record(symbol,shell)
        return shell
    def summary(self,x):
        d=x['decision']; t=x['thesis']; e=x['expectations']; setup=x['trade_intelligence']['setup_status']
        return f"{x['symbol']} is {d['state']} with deterministic research score {d['score']}/100, confidence {d['confidence']}%, decision-grade coverage {d['decision_grade_coverage']}%, bull/bear evidence weight {t['bull_weight']}/{t['bear_weight']}, expectations {e['status']}, and current setup {setup}."
