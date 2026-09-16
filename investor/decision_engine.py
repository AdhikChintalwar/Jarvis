from __future__ import annotations
from dataclasses import dataclass, field, asdict, is_dataclass
from datetime import datetime, timezone
from typing import Any

@dataclass
class DecisionComponent:
    name: str
    score: float | None
    confidence: float
    coverage: float
    configured_weight: float
    effective_weight: float
    source: str
    status: str = "AVAILABLE"

@dataclass
class DecisionReport:
    score: float
    evidence_confidence: float
    evidence_coverage: float
    research_state: str
    components: dict[str, dict] = field(default_factory=dict)
    constraints: list[str] = field(default_factory=list)
    unknowns: list[str] = field(default_factory=list)
    generated_at: str = ""
    schema_version: str = "4.7"

class DecisionEngine:
    """Deterministic investment-attractiveness authority.

    This engine never calls an LLM. Missing modules are omitted rather than scored
    bearish. Unified risk enters as risk QUALITY = 100 - risk_score. Hard-risk
    evidence constrains the research state but does not rewrite underlying modules.
    """
    WEIGHTS = {
        "financial_health": .20,
        "accounting_quality": .12,
        "valuation": .15,
        "event_intelligence": .10,
        "macro_regime": .08,
        "advanced_market": .15,
        "unified_risk_quality": .20,
    }

    def evaluate(self, report: dict[str, Any]) -> DecisionReport:
        specs = {
            "financial_health": ("financial_health", ("quality_score","score"), ("evidence_confidence","confidence"), ("evidence_coverage","coverage")),
            "accounting_quality": ("accounting_quality", ("score",), ("confidence",), ("coverage",)),
            "valuation": ("valuation", ("score",), ("confidence",), ("coverage",)),
            "event_intelligence": ("event_intelligence", ("score",), ("confidence",), ("coverage",)),
            "macro_regime": ("macro_regime", ("score",), ("confidence",), ("coverage",)),
            "advanced_market": ("advanced_market", ("score",), ("confidence",), ("coverage",)),
        }
        components: dict[str, DecisionComponent] = {}
        unknowns=[]
        for name,(key,score_keys,conf_keys,cov_keys) in specs.items():
            obj=self._dict(report.get(key))
            score=self._first_num(obj,*score_keys)
            conf=self._pct(self._first_num(obj,*conf_keys))
            cov=self._pct(self._first_num(obj,*cov_keys))
            components[name]=self._component(name,score,conf,cov,key)
            if score is None: unknowns.append(name)

        risk=self._dict(report.get("unified_risk"))
        risk_score=self._first_num(risk,"risk_score")
        risk_quality=None if risk_score is None else 100.0-risk_score
        components["unified_risk_quality"]=self._component(
            "unified_risk_quality",risk_quality,
            self._pct(self._first_num(risk,"confidence")),
            self._pct(self._first_num(risk,"coverage")),"unified_risk")
        if risk_quality is None: unknowns.append("unified_risk_quality")

        available=[c for c in components.values() if c.score is not None]
        configured_available=sum(c.configured_weight for c in available)
        if not available:
            score=50.0; confidence=0.0; coverage=0.0
        else:
            # Weight is redistributed only among available modules. Confidence does
            # not alter the score itself; it is reported independently so low-quality
            # evidence cannot silently masquerade as a different investment thesis.
            score=sum(c.score*c.configured_weight for c in available)/configured_available
            confidence=sum(c.confidence*c.configured_weight for c in available)/configured_available
            coverage=configured_available*100.0
            for c in available: c.effective_weight=c.configured_weight/configured_available

        constraints=[]
        hard=list(risk.get("hard_overrides") or [])
        level=str(risk.get("risk_level") or "UNKNOWN").upper()
        if hard: constraints.append("Deterministic hard-risk override is active.")
        if level in {"EXTREME","VERY_HIGH"}: constraints.append(f"Unified risk is {level}.")
        if coverage < 60: constraints.append("Decision module coverage is below 60%.")
        if confidence < 45: constraints.append("Evidence confidence is below 45%.")

        state=self._state(score)
        # State is research prioritization, not a buy/sell order.
        if hard or level=="EXTREME": state=min((state,"WATCH"),key=self._state_rank)
        elif level=="VERY_HIGH": state=min((state,"WATCH"),key=self._state_rank)
        if coverage<60 or confidence<45: state=min((state,"WATCH"),key=self._state_rank)

        return DecisionReport(
            score=round(score,2), evidence_confidence=round(confidence,2),
            evidence_coverage=round(coverage,2), research_state=state,
            components={k:asdict(v) for k,v in components.items()},
            constraints=constraints, unknowns=unknowns,
            generated_at=datetime.now(timezone.utc).isoformat())

    def _component(self,name,score,conf,cov,source):
        w=self.WEIGHTS[name]
        return DecisionComponent(name,self._clamp(score),conf,cov,w,0.0,source,"AVAILABLE" if score is not None else "UNKNOWN")
    @staticmethod
    def _state(score):
        if score>=75:return "TOP_RESEARCH"
        if score>=62:return "CANDIDATE"
        if score>=48:return "WATCH"
        if score>=35:return "WAIT"
        return "AVOID"
    @staticmethod
    def _state_rank(s): return {"AVOID":0,"WAIT":1,"WATCH":2,"CANDIDATE":3,"TOP_RESEARCH":4}.get(s,2)
    @staticmethod
    def _dict(x):
        if x is None:return {}
        if isinstance(x,dict):return x
        if is_dataclass(x):return asdict(x)
        return vars(x) if hasattr(x,"__dict__") else {}
    @staticmethod
    def _first_num(d,*keys):
        for k in keys:
            v=d.get(k)
            if isinstance(v,(int,float)) and not isinstance(v,bool):return float(v)
        return None
    @staticmethod
    def _pct(v):
        if v is None:return 0.0
        return max(0.0,min(100.0,v*100 if 0<=v<=1 else v))
    @staticmethod
    def _clamp(v): return None if v is None else max(0.0,min(100.0,float(v)))
