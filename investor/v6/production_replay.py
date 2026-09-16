from types import SimpleNamespace
from dataclasses import asdict
from investor.financial_engine import FinancialEngine
from investor.decision_engine import DecisionEngine

class HistoricalProductionDecisionAdapter:
    """Uses Baby's production deterministic engines on only historically safe inputs.

    V6.0 real gate intentionally replays the financial-health component first.
    Missing historical modules stay UNKNOWN; DecisionEngine therefore reports low
    module coverage rather than pretending a full historical recommendation.
    """
    def __init__(self):
        self.financial=FinancialEngine()
        self.decision=DecisionEngine()

    @staticmethod
    def _ev(snapshot,name):
        return snapshot.evidence.get(name)

    def __call__(self,snapshot):
        rev=self._ev(snapshot,"revenue"); ni=self._ev(snapshot,"net_income")
        ocf=self._ev(snapshot,"operating_cash_flow"); fcf=self._ev(snapshot,"free_cash_flow")
        cash=self._ev(snapshot,"cash"); debt=self._ev(snapshot,"debt")

        net_margin=None
        if rev and ni and rev.period_end==ni.period_end and rev.value not in (None,0):
            net_margin=float(ni.value)/float(rev.value)

        f=SimpleNamespace(
            revenue_growth=None,
            profit_margin=net_margin,
            operating_margin=None,
            free_cash_flow=fcf.value if fcf else None,
            operating_cash_flow=ocf.value if ocf else None,
            total_cash=cash.value if cash else None,
            total_debt=debt.value if debt else None,
        )
        verified={}
        mapping={
            "net_margin": (net_margin, rev or ni),
            "free_cash_flow": (fcf.value if fcf else None, fcf),
            "operating_cash_flow": (ocf.value if ocf else None, ocf),
            "cash": (cash.value if cash else None, cash),
            "debt": (debt.value if debt else None, debt),
        }
        for name,(value,e) in mapping.items():
            if value is not None and e is not None:
                verified[name]={"value":value,"status":"PRIMARY_ONLY","confidence":.85,
                                "period":e.period_end,"source":e.source}
        # Deliberately unresolved until multi-period coherent resolver exists.
        for name in ("revenue_growth_yoy","operating_margin"):
            verified[name]={"value":None,"status":"MISSING","confidence":0}

        primary={"verified_financials":verified}
        fh=self.financial.analyze(f,primary)
        dr=self.decision.evaluate({"financial_health":asdict(fh)})
        out=asdict(dr)
        out["state"]=out.pop("research_state")
        out["confidence"]=out.pop("evidence_confidence")
        out["coverage"]=out.pop("evidence_coverage")
        out["risk_level"]="UNKNOWN"
        out["hard_override"]=False
        out["replay_scope"]="PARTIAL_PRODUCTION_FINANCIAL_HEALTH"
        return out
