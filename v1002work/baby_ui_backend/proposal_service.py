from __future__ import annotations

import math
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


@dataclass
class PaperProposal:
    symbol: str
    status: str
    eligible: bool
    reason: str
    research_decision: str
    research_score: float|None
    confidence: float|None
    coverage: float|None
    risk_level: str
    hard_risk_override: bool
    setup_status: str
    quote_price: float|None
    quote_quality: str
    quote_provider: str
    quote_as_of: str|None
    entry_price: float|None
    invalidation: float|None
    target_1: float|None
    target_2: float|None
    risk_per_share: float|None
    account_equity: float|None
    cash_available: float|None
    risk_budget_percent: float
    risk_budget_dollars: float|None
    max_position_percent: float
    max_position_dollars: float|None
    unified_risk_multiplier: float
    proposed_quantity: float|None
    proposed_notional: float|None
    order_type: str
    warnings: list[str]
    ai_scoring_authority: float=0.0
    ai_execution_authority: str='NONE'
    real_money_execution: str='DISABLED'

    def to_dict(self): return asdict(self)


class PaperProposalService:
    """Deterministic bridge: production research -> current paper-account constraints.

    This class proposes only. It cannot fill an order and has no brokerage API.
    A setup must be actually triggered by the production TradePlanAgent before a BUY
    proposal can become ELIGIBLE. CANDIDATE/WATCH alone is never enough.
    """
    def __init__(self, base_risk_percent:float=.5, max_position_percent:float=10.0):
        self.base_risk_percent=float(base_risk_percent)
        self.max_position_percent=float(max_position_percent)

    def build(self, symbol:str, research:dict[str,Any], quote:dict[str,Any], portfolio:dict[str,Any]):
        symbol=symbol.upper()
        decision=_upper(research.get('decision'))
        score=_num(research.get('score')); confidence=_num(research.get('confidence')); coverage=_num(research.get('coverage'))
        risk=_upper(research.get('risk')); hard=bool(research.get('hard_risk_override'))
        trade=research.get('trade_plan') or {}
        current=trade.get('current_setup') or {}
        setup=_upper(current.get('status') or trade.get('status'))
        qpx=_num(quote.get('price')); quality=_upper(quote.get('quality')); provider=str(quote.get('provider') or quote.get('source') or 'UNKNOWN')
        asof=quote.get('timestamp') or quote.get('as_of')
        account=portfolio.get('account') or {}; equity=_num(account.get('equity')); cash=_num(account.get('cash'))
        warnings=[]

        # Risk multiplier is exported by the production trade sizing packet when available.
        pos=trade.get('position') or {}
        mult=_num(pos.get('unified_risk_multiplier'))
        if mult is None:
            raw=((research.get('raw') or {}).get('production_result') or {})
            ur=raw.get('unified_risk') or {}
            mult=_num(ur.get('position_risk_multiplier')) or 1.0
        mult=max(0.0,min(mult,1.0))

        entry=stop=t1=t2=None
        if setup=='AT_PULLBACK_ZONE':
            s=trade.get('pullback') or {}; entry=qpx or _num(s.get('planned_entry')); stop=_num(s.get('invalidation')); t1=_num(s.get('target_1')); t2=_num(s.get('target_2'))
        elif setup=='BREAKOUT_TRIGGERED':
            s=trade.get('breakout') or {}; entry=qpx or _num(s.get('trigger')); stop=_num(s.get('invalidation')); t1=_num(s.get('target_1')); t2=_num(s.get('target_2'))

        risk_per_share=(entry-stop) if entry is not None and stop is not None and entry>stop else None
        risk_pct=max(.05,self.base_risk_percent*mult)
        max_pct=max(0.0,self.max_position_percent*mult)
        risk_dollars=equity*risk_pct/100 if equity is not None else None
        max_dollars=equity*max_pct/100 if equity is not None else None
        qty=None
        if all(x is not None and x>0 for x in (entry,risk_per_share,risk_dollars,max_dollars,cash)):
            by_risk=risk_dollars/risk_per_share
            by_cap=max_dollars/entry
            by_cash=cash/entry
            qty=max(0.0,math.floor(min(by_risk,by_cap,by_cash)))
            if qty<=0: qty=None
        notional=qty*entry if qty is not None and entry is not None else None

        eligible=True; reason='All deterministic paper-proposal gates passed.'
        if decision not in {'TOP_RESEARCH','CANDIDATE','WATCH'}:
            eligible=False; reason=f'Decision state {decision} does not permit a new-long paper proposal.'
        if hard or risk in {'VERY_HIGH','EXTREME'}:
            eligible=False; reason='Unified-risk constraint blocks a new-long paper proposal.'
        if setup not in {'AT_PULLBACK_ZONE','BREAKOUT_TRIGGERED'}:
            eligible=False; reason=f'Production trade setup is {setup}; entry condition has not triggered.'
        if qpx is None:
            eligible=False; reason='Current quote is unavailable; Baby will not size or propose an entry.'
        if quality in {'UNKNOWN','STALE'}:
            eligible=False; reason=f'Quote quality is {quality}; fresh-enough market evidence is required.'
        if risk_per_share is None:
            eligible=False; reason='No valid entry/invalidation risk structure is available.'
        if equity is None or cash is None:
            eligible=False; reason='Paper-account equity/cash is unavailable.'
        # Quantity is only a meaningful gate after an entry setup is active and structurally valid.
        # Do not overwrite the more important 'entry not triggered' reason with a sizing symptom.
        if setup in {'AT_PULLBACK_ZONE','BREAKOUT_TRIGGERED'} and risk_per_share is not None and equity is not None and cash is not None and qty is None:
            eligible=False; reason='Portfolio/risk constraints do not allow a positive whole-share position size.'
        if coverage is not None and coverage < 50:
            eligible=False; reason=f'Evidence coverage {coverage:.1f}% is below the 50% proposal floor.'
        # Current setup is the final entry gate. When it is inactive, that is the canonical
        # reason for WAITING regardless of downstream fields that are naturally absent.
        if setup not in {'AT_PULLBACK_ZONE','BREAKOUT_TRIGGERED'}:
            eligible=False; reason=f'Production trade setup is {setup}; entry condition has not triggered.'
        if quality=='DELAYED': warnings.append('Quote is DELAYED; this is a paper simulation, not a live execution feed.')
        if provider=='YFINANCE_SECONDARY': warnings.append('Yahoo/yfinance is secondary/prototype market data, not primary execution data.')
        if decision=='WATCH': warnings.append('WATCH is permitted only when the production trade setup itself is triggered; WATCH alone never creates eligibility.')

        return PaperProposal(symbol,'ELIGIBLE' if eligible else 'WAITING',eligible,reason,decision,score,confidence,coverage,risk,hard,setup,qpx,quality,provider,asof,entry,stop,t1,t2,risk_per_share,equity,cash,risk_pct,risk_dollars,max_pct,max_dollars,mult,qty,notional,'MARKET',warnings).to_dict()
