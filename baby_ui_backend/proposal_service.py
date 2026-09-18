from __future__ import annotations

import math
import os
from dataclasses import dataclass, asdict
from typing import Any


def _num(v):
    try:
        x=float(v)
        return x if math.isfinite(x) else None
    except (TypeError,ValueError):
        return None


def _upper(v, default='UNKNOWN'):
    return str(v if v not in (None,'') else default).upper()


def _rr(entry, stop, target):
    e,s,t=map(_num,(entry,stop,target))
    if None in (e,s,t) or e <= s or t <= e:
        return None
    return (t-e)/(e-s)


@dataclass
class PaperProposal:
    symbol: str; status: str; eligible: bool; reason: str
    research_decision: str; research_score: float|None; confidence: float|None; coverage: float|None
    risk_level: str; hard_risk_override: bool; setup_status: str
    quote_price: float|None; quote_quality: str; quote_provider: str; quote_as_of: str|None
    entry_price: float|None; invalidation: float|None; target_1: float|None; target_2: float|None
    risk_per_share: float|None; account_equity: float|None; cash_available: float|None
    risk_budget_percent: float; risk_budget_dollars: float|None; max_position_percent: float; max_position_dollars: float|None
    unified_risk_multiplier: float; proposed_quantity: float|None; proposed_notional: float|None; order_type: str
    warnings: list[str]
    rr_target_1: float|None=None; rr_target_2: float|None=None
    minimum_rr_target_1: float|None=None; minimum_rr_target_2: float|None=None
    trade_quality_status: str='UNKNOWN'; execution_quote_status: str='UNKNOWN'
    gate_failures: list[str]|None=None; sizing_candidate_quantity: float|None=None
    ai_scoring_authority: float=0.0; ai_execution_authority: str='NONE'; real_money_execution: str='DISABLED'
    def to_dict(self): return asdict(self)


class PaperProposalService:
    """Deterministic research-to-paper proposal gate. Proposal only; never executes."""
    def __init__(self, base_risk_percent:float=.5, max_position_percent:float=10.0,
                 *, enforce_trade_quality:bool=False, require_execution_grade:bool=False,
                 revalidate_setup:bool=False, min_rr_target_1:float|None=None, min_rr_target_2:float|None=None):
        self.base_risk_percent=float(base_risk_percent)
        self.max_position_percent=float(max_position_percent)
        self.enforce_trade_quality=bool(enforce_trade_quality)
        self.require_execution_grade=bool(require_execution_grade)
        self.revalidate_setup=bool(revalidate_setup)
        self.min_rr_target_1=float(min_rr_target_1 if min_rr_target_1 is not None else os.getenv('BABY_MIN_RR_TARGET_1','1.0'))
        self.min_rr_target_2=float(min_rr_target_2 if min_rr_target_2 is not None else os.getenv('BABY_MIN_RR_TARGET_2','2.0'))

    def _effective_setup(self, trade:dict[str,Any], qpx:float|None):
        current=trade.get('current_setup') or {}
        setup=_upper(current.get('status') or trade.get('status'))
        if not self.revalidate_setup or qpx is None:
            return setup, current.get('reason')
        if setup=='AT_PULLBACK_ZONE':
            s=trade.get('pullback') or {}; lo=_num(s.get('entry_low')); hi=_num(s.get('entry_high'))
            if lo is not None and hi is not None and not (lo <= qpx <= hi):
                return 'WAIT_FOR_PULLBACK_OR_BREAKOUT', f'Current execution quote {qpx:.2f} is outside pullback zone {lo:.2f}-{hi:.2f}.'
        elif setup=='BREAKOUT_TRIGGERED':
            trigger=_num((trade.get('breakout') or {}).get('trigger'))
            if trigger is not None and qpx < trigger:
                return 'WAIT_FOR_PULLBACK_OR_BREAKOUT', f'Current execution quote {qpx:.2f} is below breakout trigger {trigger:.2f}.'
        return setup, current.get('reason')

    def build(self, symbol:str, research:dict[str,Any], quote:dict[str,Any], portfolio:dict[str,Any]):
        symbol=symbol.upper(); warnings=[]; failures=[]
        decision=_upper(research.get('decision')); score=_num(research.get('score')); confidence=_num(research.get('confidence')); coverage=_num(research.get('coverage'))
        risk=_upper(research.get('risk')); hard=bool(research.get('hard_risk_override')); trade=research.get('trade_plan') or {}
        qpx=_num(quote.get('price')); quality=_upper(quote.get('quality')); provider=str(quote.get('provider') or quote.get('source') or 'UNKNOWN'); asof=quote.get('timestamp') or quote.get('as_of')
        setup, setup_reason=self._effective_setup(trade,qpx)
        account=portfolio.get('account') or {}; equity=_num(account.get('equity')); cash=_num(account.get('cash'))

        pos=trade.get('position') or {}; mult=_num(pos.get('unified_risk_multiplier'))
        if mult is None:
            raw=((research.get('raw') or {}).get('production_result') or {}); ur=raw.get('unified_risk') or {}; mult=_num(ur.get('position_risk_multiplier')) or 1.0
        mult=max(0.0,min(mult,1.0))

        entry=stop=t1=t2=None
        if setup=='AT_PULLBACK_ZONE':
            s=trade.get('pullback') or {}; entry=qpx or _num(s.get('planned_entry')); stop=_num(s.get('invalidation')); t1=_num(s.get('target_1')); t2=_num(s.get('target_2'))
        elif setup=='BREAKOUT_TRIGGERED':
            s=trade.get('breakout') or {}; entry=qpx or _num(s.get('trigger')); stop=_num(s.get('invalidation')); t1=_num(s.get('target_1')); t2=_num(s.get('target_2'))

        risk_per_share=(entry-stop) if entry is not None and stop is not None and entry>stop else None
        rr1=_rr(entry,stop,t1); rr2=_rr(entry,stop,t2)
        # V15.4: trade-plan risk structure is evaluated, but Baby does not choose quantity.
        risk_pct=max(.05,self.base_risk_percent*mult); max_pct=max(0.0,self.max_position_percent*mult)
        risk_dollars=None; max_dollars=None; sizing_qty=None

        active=setup in {'AT_PULLBACK_ZONE','BREAKOUT_TRIGGERED'}
        if not active: failures.append(f'SETUP_NOT_ACTIVE:{setup}')
        if decision not in {'TOP_RESEARCH','CANDIDATE','WATCH'}: failures.append(f'DECISION_BLOCK:{decision}')
        if hard or risk in {'VERY_HIGH','EXTREME'}: failures.append('UNIFIED_RISK_BLOCK')
        if qpx is None: failures.append('QUOTE_UNAVAILABLE')
        if quality in {'UNKNOWN','STALE'}: failures.append(f'QUOTE_QUALITY:{quality}')
        if risk_per_share is None: failures.append('INVALID_RISK_STRUCTURE')
        if coverage is not None and coverage < 50: failures.append('EVIDENCE_COVERAGE_BELOW_FLOOR')

        trade_quality='NOT_EVALUATED'
        if self.enforce_trade_quality and active:
            trade_quality='PASS'
            if rr1 is None or rr1 < self.min_rr_target_1:
                failures.append('RR_TARGET_1_BELOW_MINIMUM'); trade_quality='BLOCKED'
            if rr2 is None or rr2 < self.min_rr_target_2:
                failures.append('RR_TARGET_2_BELOW_MINIMUM'); trade_quality='BLOCKED'
            if t1 is None or entry is None or t1 <= entry:
                failures.append('TARGET_1_NOT_ABOVE_ENTRY'); trade_quality='BLOCKED'
            if t2 is None or entry is None or t2 <= entry:
                failures.append('TARGET_2_NOT_ABOVE_ENTRY'); trade_quality='BLOCKED'

        execution_ok=bool(quote.get('execution_eligible'))
        execution_status='PASS' if execution_ok else 'BLOCKED'
        if self.require_execution_grade and not execution_ok:
            failures.append('EXECUTION_QUOTE_NOT_ELIGIBLE')

        failures=list(dict.fromkeys(failures)); eligible=not failures
        if eligible:
            reason='All deterministic setup-readiness gates passed. Quantity is user-selected.'; status='ELIGIBLE'
        elif not active:
            reason=f'Production trade setup is {setup}; entry condition has not triggered.'; status='WAITING'
        elif 'UNIFIED_RISK_BLOCK' in failures:
            reason='Unified-risk constraint blocks a new-long paper proposal.'; status='BLOCKED'
        elif 'RR_TARGET_1_BELOW_MINIMUM' in failures or 'RR_TARGET_2_BELOW_MINIMUM' in failures:
            reason=(f'Trade quality does not meet minimum risk/reward policy: '
                    f'R:R T1={rr1:.2f}' if rr1 is not None else 'Trade quality does not meet minimum risk/reward policy: R:R T1=UNKNOWN')
            reason += f' (min {self.min_rr_target_1:.2f}), R:R T2={rr2:.2f}' if rr2 is not None else f' (min {self.min_rr_target_1:.2f}), R:R T2=UNKNOWN'
            reason += f' (min {self.min_rr_target_2:.2f}).'; status='BLOCKED'
        elif 'EXECUTION_QUOTE_NOT_ELIGIBLE' in failures:
            issues=', '.join(quote.get('validation_issues') or []) or 'quote did not pass execution validation'
            reason=f'Active research setup exists, but current quote is not execution-grade: {issues}.'; status='RESEARCH_SETUP_ONLY'
        elif 'DECISION_BLOCK:'+decision in failures:
            reason=f'Decision state {decision} does not permit a new-long paper proposal.'; status='BLOCKED'
        elif 'EVIDENCE_COVERAGE_BELOW_FLOOR' in failures:
            reason=f'Evidence coverage {coverage:.1f}% is below the 50% proposal floor.'; status='BLOCKED'
        else:
            reason='One or more deterministic proposal gates failed.'; status='BLOCKED'

        if quality=='DELAYED': warnings.append('Quote is DELAYED and cannot be execution-grade under the strict V10.0.3 gate.')
        if provider.upper()=='YFINANCE_SECONDARY': warnings.append('Yahoo/yfinance is secondary/prototype research data and cannot authorize a paper entry.')
        if decision=='WATCH': warnings.append('WATCH is permitted only when every setup, trade-quality, execution-data, and risk gate passes.')
        if setup_reason and setup != _upper((trade.get('current_setup') or {}).get('status') or trade.get('status')): warnings.append(setup_reason)

        # V15.4: Baby never proposes a share count or notional.
        qty=None; notional=None
        warnings.append('ORDER_QUANTITY_USER_SELECTED: Baby does not choose the PAPER order quantity.')
        return PaperProposal(symbol,status,eligible,reason,decision,score,confidence,coverage,risk,hard,setup,qpx,quality,provider,asof,entry,stop,t1,t2,risk_per_share,equity,cash,risk_pct,risk_dollars,max_pct,max_dollars,mult,qty,notional,'MARKET',warnings,
                             round(rr1,2) if rr1 is not None else None,round(rr2,2) if rr2 is not None else None,self.min_rr_target_1,self.min_rr_target_2,trade_quality,execution_status,failures,sizing_qty).to_dict()
