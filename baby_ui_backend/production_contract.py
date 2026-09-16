from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any


class ProductionContractError(RuntimeError):
    pass


def _dict(x: Any) -> dict:
    if x is None:
        return {}
    if isinstance(x, dict):
        return x
    if hasattr(x, '__dict__'):
        return dict(vars(x))
    return {}


@dataclass
class ProductionContract:
    status: str
    decision_present: bool
    validation_present: bool
    trade_plan_present: bool
    decision_state: str
    trade_setup: str
    reason: str

    def to_dict(self):
        return asdict(self)


def validate_investment_result(result: Any, history_rows: int) -> ProductionContract:
    decision = _dict(getattr(result, 'decision', None))
    validation = _dict(getattr(result, 'validation', None))
    trade = _dict(getattr(result, 'trade_plan', None))

    if not decision:
        raise ProductionContractError('DecisionEngine produced no decision packet.')
    if 'research_state' not in decision or 'score' not in decision:
        raise ProductionContractError('DecisionEngine packet is missing research_state or score.')
    if not validation:
        raise ProductionContractError('ValidationEngine produced no validation packet.')

    state = str(decision.get('research_state') or 'UNKNOWN').upper()
    if history_rows >= 50:
        if not trade:
            raise ProductionContractError(
                f'TradePlanAgent produced no trade plan despite {history_rows} valid OHLC rows.'
            )
        current = _dict(trade.get('current_setup'))
        setup = str(current.get('status') or trade.get('status') or 'UNKNOWN').upper()
        if setup == 'UNKNOWN':
            raise ProductionContractError('TradePlanAgent packet has no current setup status.')
        reason = 'Decision, validation, and trade-plan production contracts satisfied.'
    else:
        setup = 'NOT_PRODUCED'
        reason = f'Trade plan not produced: {history_rows} OHLC rows available; 50 required.'

    return ProductionContract(
        status='PASS',
        decision_present=True,
        validation_present=True,
        trade_plan_present=bool(trade),
        decision_state=state,
        trade_setup=setup,
        reason=reason,
    )
