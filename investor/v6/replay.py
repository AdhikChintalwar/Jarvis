from dataclasses import dataclass,asdict
from typing import Any,Callable,Dict,Optional

@dataclass
class HistoricalDecision:
    symbol:str; as_of:str; score:Optional[float]; state:str
    confidence:Optional[float]; coverage:Optional[float]
    risk_level:Optional[str]; hard_override:bool
    evidence_count:int; model_version:str="6.0"
    metadata:Dict[str,Any]=None
    def to_dict(self): return asdict(self)

class HistoricalDecisionReplay:
    """Adapter between point-in-time snapshots and Baby's deterministic decision stack.

    `decision_fn` is injected so V6 never silently substitutes a toy score for the
    production DecisionEngine. It must consume only the supplied PIT snapshot.
    """
    def __init__(self,decision_fn:Callable):
        self.decision_fn=decision_fn

    def replay(self,snapshot):
        if snapshot.provenance.get("blocked_future_evidence"):
            # Blocking is expected; blocked evidence is NOT passed downstream.
            pass
        result=self.decision_fn(snapshot)
        if isinstance(result,dict): d=result
        else: d=getattr(result,"__dict__",{})
        return HistoricalDecision(
            symbol=snapshot.symbol,as_of=snapshot.as_of,
            score=d.get("score",d.get("decision_score")),
            state=str(d.get("state",d.get("decision","UNKNOWN"))),
            confidence=d.get("confidence",d.get("evidence_confidence")),
            coverage=d.get("coverage",d.get("evidence_coverage")),
            risk_level=d.get("risk_level"),
            hard_override=bool(d.get("hard_override",False)),
            evidence_count=len(snapshot.evidence),
            metadata={"snapshot_schema":snapshot.provenance.get("schema_version")}
        )
