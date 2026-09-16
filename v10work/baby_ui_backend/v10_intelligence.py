from __future__ import annotations
import json, math
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any


def _num(x):
    try:
        v=float(x); return v if math.isfinite(v) else None
    except (TypeError,ValueError): return None

def _up(x, default='UNKNOWN'): return str(x if x not in (None,'') else default).upper()

def _rr(entry, stop, target):
    e,s,t=map(_num,(entry,stop,target))
    if None in (e,s,t) or e<=s or t<=e: return None
    return round((t-e)/(e-s),2)

@dataclass
class ExitPolicy:
    status:str; setup:str; entry:float|None; initial_invalidation:float|None
    target_1:float|None; target_2:float|None; rr_target_1:float|None; rr_target_2:float|None
    partial_exit_1_percent:float; partial_exit_2_percent:float
    trailing_stop_after_target_1:str; thesis_exit:str; time_exit:str; event_risk_exit:str
    authority:str='DETERMINISTIC_POLICY'; ai_authority:str='NONE'
    def to_dict(self): return asdict(self)

class V10IntelligenceService:
    """Read-only V10 intelligence projection over production Baby research.

    It does NOT create a second investment score. DecisionEngine/UnifiedRisk/TradePlanAgent
    remain authoritative. This layer exposes the complete research -> setup -> exit lifecycle.
    """
    def __init__(self, report_dir='data/ui_research'):
        self.report_dir=Path(report_dir)

    def load(self,symbol:str)->dict[str,Any]:
        p=self.report_dir/f'{symbol.upper()}.json'
        if not p.exists(): return {'symbol':symbol.upper(),'status':'NOT_RESEARCHED'}
        return json.loads(p.read_text())

    def exit_policy(self,research:dict[str,Any])->dict[str,Any]:
        trade=research.get('trade_plan') or {}; current=trade.get('current_setup') or {}
        setup=_up(current.get('status') or trade.get('status'))
        block=None
        if setup=='AT_PULLBACK_ZONE': block=trade.get('pullback') or {}
        elif setup=='BREAKOUT_TRIGGERED': block=trade.get('breakout') or {}
        else:
            # Still expose both deterministic scenarios, but never pretend one is active.
            block={}
        entry=_num((research.get('quote') or {}).get('price')) or _num(block.get('planned_entry')) or _num(block.get('trigger'))
        stop=_num(block.get('invalidation')); t1=_num(block.get('target_1')); t2=_num(block.get('target_2'))
        valid=setup in {'AT_PULLBACK_ZONE','BREAKOUT_TRIGGERED'} and entry is not None and stop is not None and entry>stop
        return ExitPolicy(
            status='ACTIVE_POLICY' if valid else 'WAIT_FOR_VALID_ENTRY', setup=setup,
            entry=entry, initial_invalidation=stop, target_1=t1, target_2=t2,
            rr_target_1=_rr(entry,stop,t1), rr_target_2=_rr(entry,stop,t2),
            partial_exit_1_percent=50.0, partial_exit_2_percent=25.0,
            trailing_stop_after_target_1='For the remaining position, trail using the production invalidation/structure; never loosen the stop below the original invalidation.',
            thesis_exit='Exit remaining paper position when a production hard-risk override appears or the deterministic thesis becomes invalid.',
            time_exit='REVIEW_REQUIRED: no universal time stop is imposed without strategy-specific historical validation.',
            event_risk_exit='REVIEW_REQUIRED before earnings/material corporate events; Baby does not invent an event-risk rule without evidence.'
        ).to_dict()

    def full_flow(self,symbol:str, quote:dict|None=None, portfolio:dict|None=None, proposal:dict|None=None)->dict[str,Any]:
        r=self.load(symbol)
        if r.get('status')=='NOT_RESEARCHED': return r
        stages={x.get('id'):x for x in (r.get('stages') or []) if isinstance(x,dict)}
        trade=r.get('trade_plan') or {}; current=trade.get('current_setup') or {}
        flow={
          'symbol':symbol.upper(),'status':'READY','research':{
            'decision':r.get('decision'),'score':r.get('score'),'confidence':r.get('confidence'),'coverage':r.get('coverage'),
            'risk':r.get('risk'),'hard_risk_override':r.get('hard_risk_override'),'validation_status':r.get('validation_status')},
          'intelligence':{
            'financial_health':stages.get('financials',{}),'accounting_quality':stages.get('accounting',{}),
            'valuation':stages.get('valuation',{}),'technical':stages.get('technical',{}),
            'liquidity':stages.get('liquidity',{}),'sec_events':stages.get('sec',{}),'macro':stages.get('macro',{}),
            'unified_risk':stages.get('risk',{}),'independent_validation':stages.get('validation',{})},
          'trade_plan':trade,
          'current_setup':current,
          'exit_policy':self.exit_policy({**r,'quote':quote or {}}),
          'paper_proposal':proposal,
          'portfolio':portfolio,
          'authority':{'PRIMARY_FACTS':'SOURCE_EVIDENCE','DERIVED_METRICS':'BABY_DETERMINISTIC','RESEARCH_SCORE':'BABY_DECISION_ENGINE','TRADE_LEVELS':'BABY_TRADE_PLAN_AGENT','AI_SCORING':'0%','AI_EXECUTION':'NONE','REAL_MONEY':'DISABLED'},
          'warnings':[]
        }
        if not trade: flow['warnings'].append('No production trade plan is available.')
        if _up(current.get('status')) not in {'AT_PULLBACK_ZONE','BREAKOUT_TRIGGERED'}:
            flow['warnings'].append('No entry is currently triggered; displayed pullback/breakout levels are research scenarios, not an active entry.')
        if r.get('hard_risk_override'): flow['warnings'].append('Hard risk override is active; new-long proposal must remain blocked.')
        return flow
