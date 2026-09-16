from __future__ import annotations
import json, math
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

ACTIVE_SETUPS={'AT_PULLBACK_ZONE','BREAKOUT_TRIGGERED'}

def _num(x):
    try:
        v=float(x); return v if math.isfinite(v) else None
    except (TypeError,ValueError): return None

def _up(x, default='UNKNOWN'): return str(x if x not in (None,'') else default).upper()

def _rr(entry, stop, target):
    e,s,t=map(_num,(entry,stop,target))
    if None in (e,s,t) or e<=s or t<=e: return None
    return round((t-e)/(e-s),2)

def _metric_has_evidence(m:dict[str,Any])->bool:
    if _num(m.get('value')) is not None: return True
    if any(v not in (None,'','UNKNOWN') for v in (m.get('inputs') or {}).values()): return True
    for p in m.get('provenance') or []:
        if p.get('verified') is True or _up(p.get('status')) in {'PASS','VERIFIED'}: return True
    return False

def _stage_with_lineage(stage:dict[str,Any])->dict[str,Any]:
    """Never present a scored PASS as fully evidenced when the exported metrics cannot support it."""
    s=dict(stage or {})
    metrics=[dict(m) for m in (s.get('metrics') or []) if isinstance(m,dict)]
    score=_num(s.get('score')); production_status=_up(s.get('status'))
    evidenced=sum(1 for m in metrics if _metric_has_evidence(m))
    if score is not None and metrics and evidenced==0:
        s['production_status']=production_status
        s['status']='EVIDENCE_LINEAGE_INCOMPLETE'
        s['lineage']={
            'status':'INCOMPLETE','exported_metric_count':len(metrics),'evidenced_metric_count':0,
            'message':'A production score exists, but this V10 projection does not contain the evidence values needed to reconstruct it. The score is preserved but not upgraded to an evidenced PASS.'
        }
    elif score is not None:
        s['lineage']={'status':'AVAILABLE' if evidenced else 'NOT_EXPOSED','exported_metric_count':len(metrics),'evidenced_metric_count':evidenced}
    return s

def canonical_market_snapshot(symbol:str, research:dict[str,Any], quote:dict[str,Any]|None)->dict[str,Any]:
    """Single V10 run snapshot. Quote is current execution/reference evidence; trade-plan price remains explicitly historical research context."""
    quote=quote or {}; trade=research.get('trade_plan') or {}
    return {
        'symbol':symbol.upper(),
        'price':_num(quote.get('price')),
        'quality':_up(quote.get('quality')),
        'provider':quote.get('provider') or quote.get('source') or 'UNKNOWN',
        'as_of':quote.get('timestamp') or quote.get('as_of'),
        'research_price':_num(trade.get('current_price')),
        'research_price_as_of':trade.get('market_data_as_of'),
        'research_price_source':trade.get('market_data_source'),
        'rule':'All V10 current-state gates use this snapshot price. Production trade levels remain immutable research outputs.'
    }

@dataclass
class ExitPolicy:
    status:str; setup:str; entry:float|None; initial_invalidation:float|None
    target_1:float|None; target_2:float|None; rr_target_1:float|None; rr_target_2:float|None
    partial_exit_1_percent:float; partial_exit_2_percent:float
    trailing_stop_after_target_1:str; thesis_exit:str; time_exit:str; event_risk_exit:str
    authority:str='DETERMINISTIC_POLICY'; ai_authority:str='NONE'
    def to_dict(self): return asdict(self)

class V10IntelligenceService:
    def __init__(self, report_dir='data/ui_research'): self.report_dir=Path(report_dir)
    def load(self,symbol:str)->dict[str,Any]:
        p=self.report_dir/f'{symbol.upper()}.json'
        if not p.exists(): return {'symbol':symbol.upper(),'status':'NOT_RESEARCHED'}
        return json.loads(p.read_text())

    def exit_policy(self,research:dict[str,Any], snapshot:dict[str,Any]|None=None)->dict[str,Any]:
        trade=research.get('trade_plan') or {}; current=trade.get('current_setup') or {}
        setup=_up(current.get('status') or trade.get('status')); block={}
        if setup=='AT_PULLBACK_ZONE': block=trade.get('pullback') or {}
        elif setup=='BREAKOUT_TRIGGERED': block=trade.get('breakout') or {}
        active=setup in ACTIVE_SETUPS
        # No active setup => no active entry/stop/targets. Scenario levels remain in trade_plan only.
        if active:
            snap=snapshot or canonical_market_snapshot(str(research.get('symbol') or ''),research,research.get('quote') or {})
            entry=_num(snap.get('price')) or _num(block.get('planned_entry')) or _num(block.get('trigger'))
            stop=_num(block.get('invalidation')); t1=_num(block.get('target_1')); t2=_num(block.get('target_2'))
        else: entry=stop=t1=t2=None
        valid=active and entry is not None and stop is not None and entry>stop
        return ExitPolicy(
            status='ACTIVE_POLICY' if valid else 'WAIT_FOR_VALID_ENTRY',setup=setup,entry=entry,initial_invalidation=stop,
            target_1=t1,target_2=t2,rr_target_1=_rr(entry,stop,t1),rr_target_2=_rr(entry,stop,t2),
            partial_exit_1_percent=50.0,partial_exit_2_percent=25.0,
            trailing_stop_after_target_1='For the remaining position, trail using the production invalidation/structure; never loosen the stop below the original invalidation.',
            thesis_exit='Exit remaining paper position when a production hard-risk override appears or the deterministic thesis becomes invalid.',
            time_exit='REVIEW_REQUIRED: no universal time stop is imposed without strategy-specific historical validation.',
            event_risk_exit='REVIEW_REQUIRED before earnings/material corporate events; Baby does not invent an event-risk rule without evidence.'
        ).to_dict()

    def full_flow(self,symbol:str, quote:dict|None=None, portfolio:dict|None=None, proposal:dict|None=None)->dict[str,Any]:
        r=self.load(symbol)
        if r.get('status')=='NOT_RESEARCHED': return r
        stages={x.get('id'):_stage_with_lineage(x) for x in (r.get('stages') or []) if isinstance(x,dict)}
        trade=r.get('trade_plan') or {}; current=trade.get('current_setup') or {}
        snapshot=canonical_market_snapshot(symbol,r,quote)
        portfolio_view=dict(portfolio or {})
        if portfolio_view.get('orders'):
            portfolio_view['order_context']={
                'existing_order_count':len(portfolio_view.get('orders') or []),
                'classification':'EXISTING_PAPER_ORDERS_NOT_CREATED_BY_THIS_V10_FLOW',
                'current_flow_created_order':False,
                'message':'Orders shown here pre-existed this read-only full-flow request. A proposal never creates an order.'
            }
        flow={
          'symbol':symbol.upper(),'status':'READY','market_snapshot':snapshot,
          'research':{'decision':r.get('decision'),'score':r.get('score'),'confidence':r.get('confidence'),'coverage':r.get('coverage'),'risk':r.get('risk'),'hard_risk_override':r.get('hard_risk_override'),'validation_status':r.get('validation_status')},
          'intelligence':{'financial_health':stages.get('financials',{}),'accounting_quality':stages.get('accounting',{}),'valuation':stages.get('valuation',{}),'technical':stages.get('technical',{}),'liquidity':stages.get('liquidity',{}),'sec_events':stages.get('sec',{}),'macro':stages.get('macro',{}),'unified_risk':stages.get('risk',{}),'independent_validation':stages.get('validation',{})},
          'trade_plan':trade,'current_setup':current,'exit_policy':self.exit_policy(r,snapshot),'paper_proposal':proposal,'portfolio':portfolio_view,
          'authority':{'PRIMARY_FACTS':'SOURCE_EVIDENCE','DERIVED_METRICS':'BABY_DETERMINISTIC','RESEARCH_SCORE':'BABY_DECISION_ENGINE','TRADE_LEVELS':'BABY_TRADE_PLAN_AGENT','AI_SCORING':'0%','AI_EXECUTION':'NONE','REAL_MONEY':'DISABLED'},'warnings':[]}
        if not trade: flow['warnings'].append('No production trade plan is available.')
        if _up(current.get('status')) not in ACTIVE_SETUPS: flow['warnings'].append('No entry is currently triggered; displayed pullback/breakout levels are research scenarios, not an active entry.')
        if r.get('hard_risk_override'): flow['warnings'].append('Hard risk override is active; new-long proposal must remain blocked.')
        return flow
