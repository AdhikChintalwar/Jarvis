from __future__ import annotations
from dataclasses import asdict
from types import SimpleNamespace
from investor.financial_engine import FinancialEngine
from investor.accounting_quality import AccountingQualityEngine
from investor.valuation_engine import ValuationEngine
from investor.event_intelligence import EventIntelligenceEngine
from investor.unified_risk import UnifiedRiskEngine
from investor.decision_engine import DecisionEngine

class FullHistoricalDecisionAdapter:
    """Historical adapter for Baby's deterministic V4.x engines.

    A module is passed to DecisionEngine only when its historical inputs exist.
    Missing modules stay UNKNOWN. No LLM or current-data fallback is permitted.
    """
    def __init__(self):
        self.fin=FinancialEngine();self.acct=AccountingQualityEngine()
        self.val=ValuationEngine();self.events=EventIntelligenceEngine()
        self.risk=UnifiedRiskEngine();self.decision=DecisionEngine()

    @staticmethod
    def _verified(evidence):
        out={}
        for name,e in evidence.items():
            if name=="shares_outstanding":continue
            out[name]={"value":e.value,"status":"PRIMARY_ONLY" if e.authority=="PRIMARY" else "AGREEMENT",
                       "confidence":.85 if e.authority=="PRIMARY" else .80,
                       "period":e.period_end,"source":e.source}
        return out

    def evaluate(self,snapshot,market=None,macro=None,sec_analysis=None,annual_history=None):
        verified=self._verified(snapshot.evidence)
        primary={"verified_financials":verified,"annual_history":{"periods":annual_history or []}}
        g=lambda n: verified.get(n,{}).get("value")
        fundamentals=SimpleNamespace(
          revenue=g("revenue"),net_income=g("net_income"),free_cash_flow=g("free_cash_flow"),
          operating_cash_flow=g("operating_cash_flow"),total_cash=g("cash"),total_debt=g("debt"),
          revenue_growth=g("revenue_growth_yoy"),profit_margin=g("net_margin"),
          operating_margin=g("operating_margin"),forward_pe=None,
          shares_outstanding=(snapshot.evidence.get("shares_outstanding").value
                              if snapshot.evidence.get("shares_outstanding") else None),
          market_cap=None)
        fin=asdict(self.fin.analyze(fundamentals,primary))
        acct=asdict(self.acct.analyze(primary))
        report={"financial_health":fin,"accounting_quality":acct}
        if market is not None:
            m=SimpleNamespace(current_price=market.current_price,price=market.current_price,
                              as_of=market.as_of)
            val=asdict(self.val.analyze(m,fundamentals,primary))
            report["valuation"]=val
            report["advanced_market"]=market.advanced_market
            report["market_data"]={"current_price":market.current_price,"price":market.current_price,
              "average_volume_20d":market.average_volume_20d,
              "average_dollar_volume_20d":market.average_dollar_volume_20d}
            report["liquidity_evidence"]={"average_dollar_volume_20d":market.average_dollar_volume_20d,
                                         "source":market.source,"as_of":market.as_of}
        if macro is not None:report["macro_regime"]=macro
        if sec_analysis is not None:
            report["event_intelligence"]=asdict(self.events.analyze(sec_analysis=sec_analysis,
                                      news_items=[],now=None))
        # Risk sees only historically present modules.
        report["unified_risk"]=asdict(self.risk.analyze(report))
        d=asdict(self.decision.evaluate(report))
        d["report"]=report
        d["historical_module_coverage"]=d["evidence_coverage"]
        d["ai_scoring_authority"]=0.0;d["ai_execution_authority"]=0.0
        return d
