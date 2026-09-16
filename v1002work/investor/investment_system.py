from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any
import pandas as pd
from investor.decision_engine import DecisionEngine
from investor.validation_engine import ValidationEngine
from investor.trade_plan_v46 import TradePlanAgent
from investor.providers.alpha_vantage_provider import AlphaVantageProvider

@dataclass
class InvestmentSystemResult:
    symbol: str
    decision: dict
    validation: dict
    trade_plan: dict | None
    external_provider: dict | None = None
    ai_role: str = "RESEARCH_RED_TEAM_ONLY"
    ai_scoring_authority: float = 0.0
    execution_authority: str = "NONE"
    schema_version: str = "4.8.5"

class BabyInvestmentSystem:
    """Deterministic decision + validation + trade-plan orchestration.

    Alpha Vantage is independent SECONDARY validation only. It never becomes a
    scoring input and never overwrites SEC/XBRL primary facts. LLM authority is 0%.
    """
    def __init__(self, external_provider:AlphaVantageProvider|None=None, auto_external:bool=True):
        self.decision_engine=DecisionEngine()
        self.validation_engine=ValidationEngine()
        self.trade_agent=TradePlanAgent()
        self.external_provider=external_provider or AlphaVantageProvider()
        self.auto_external=bool(auto_external)

    def evaluate(self, report:dict[str,Any], history:pd.DataFrame|None=None,
                 external_reference:dict[str,Any]|None=None, account_size:float|None=None,
                 base_risk_percent:float=.5, max_position_percent:float=10.0)->InvestmentSystemResult:
        decision=self.decision_engine.evaluate(report)
        symbol=str(report.get("ticker") or "").upper()

        provider_meta=None
        ext=external_reference
        if ext is None and self.auto_external and symbol:
            try:
                ext=self.external_provider.build_reference(symbol)
            except Exception as exc:
                ext={"source":"Alpha Vantage","provider":"ALPHA_VANTAGE","independent":True,
                     "status":"UNAVAILABLE","warnings":[f"{type(exc).__name__}: {exc}"]}
        if ext:
            provider_meta={
                "provider":ext.get("provider") or ext.get("source"),
                "source":ext.get("source"),
                "independent":ext.get("independent") is True,
                "status":ext.get("status"),
                "as_of":ext.get("as_of"),
                "market_as_of":ext.get("market_as_of"),
                "financial_as_of":ext.get("financial_as_of"),
                "warnings":list(ext.get("warnings") or []),
            }

        validation=self.validation_engine.validate(report,history,ext)
        trade=None
        # TradePlanAgent requires >=50 valid OHLC rows. Keep this boundary aligned
        # with the agent instead of calling it at 30 rows and raising downstream.
        if history is not None and len(history)>=50:
            trade=self.trade_agent.build(
                report,history,decision,account_size,base_risk_percent,max_position_percent
            )
        return InvestmentSystemResult(
            symbol,asdict(decision),asdict(validation),asdict(trade) if trade else None,provider_meta
        )
