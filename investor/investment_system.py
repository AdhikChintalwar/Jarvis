from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any
import pandas as pd
from investor.decision_engine import DecisionEngine
from investor.validation_engine import ValidationEngine
from investor.trade_plan_v46 import TradePlanAgent

@dataclass
class InvestmentSystemResult:
    symbol: str
    decision: dict
    validation: dict
    trade_plan: dict | None
    ai_role: str = "RESEARCH_RED_TEAM_ONLY"
    ai_scoring_authority: float = 0.0
    execution_authority: str = "NONE"
    schema_version: str = "4.7"

class BabyInvestmentSystem:
    """V4.7 sovereign deterministic decision + validation orchestration.

    LLM output is deliberately not accepted by this class as a scoring input.
    Real-money execution is outside this class and remains human-approved.
    """
    def __init__(self):
        self.decision_engine=DecisionEngine();self.validation_engine=ValidationEngine();self.trade_agent=TradePlanAgent()

    def evaluate(self, report:dict[str,Any], history:pd.DataFrame|None=None,
                 external_reference:dict[str,Any]|None=None, account_size:float|None=None,
                 base_risk_percent:float=.5, max_position_percent:float=10.0)->InvestmentSystemResult:
        decision=self.decision_engine.evaluate(report)
        validation=self.validation_engine.validate(report,history,external_reference)
        trade=None
        if history is not None and len(history)>=30:
            trade=self.trade_agent.build(report,history,decision,account_size,base_risk_percent,max_position_percent)
        return InvestmentSystemResult(str(report.get("ticker") or "").upper(),asdict(decision),asdict(validation),
                                      asdict(trade) if trade else None)
