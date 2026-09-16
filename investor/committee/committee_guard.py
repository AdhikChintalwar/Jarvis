from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


@dataclass
class CommitteeGuardReport:
    deterministic_score: float = 50.0
    evidence_authority: float = 0.0
    module_coverage: float = 0.0
    risk_score: float | None = None
    risk_level: str = "UNKNOWN"
    hard_overrides: list[str] = None
    maximum_decision: str = "TOP_CANDIDATE"
    governance_status: str = "PASS"
    constraints: list[str] = None
    module_scores: dict = None

    def __post_init__(self):
        self.hard_overrides = list(self.hard_overrides or [])
        self.constraints = list(self.constraints or [])
        self.module_scores = dict(self.module_scores or {})

    def to_dict(self):
        return asdict(self)


class FinalCommitteeGuard:
    """
    V4.4 deterministic governance layer.

    Nemotron may synthesize evidence, but it cannot:
    - erase deterministic hard-risk overrides,
    - promote a security beyond the deterministic decision ceiling,
    - replace missing evidence with confidence,
    - make the final score independent of deterministic engines.

    Score semantics:
      0..100 research attractiveness, NOT predicted return.
      Missing modules are omitted, not treated as bearish.
    """

    WEIGHTS = {
        "financial_health": 0.20,
        "accounting_quality": 0.12,
        "valuation": 0.15,
        "event_intelligence": 0.10,
        "macro_regime": 0.08,
        "advanced_market": 0.15,
        "unified_risk_quality": 0.20,
    }

    DECISION_ORDER = {
        "AVOID": 0,
        "WAIT": 1,
        "WATCH": 2,
        "CANDIDATE": 3,
        "TOP_CANDIDATE": 4,
    }

    def evaluate(self, evidence: dict) -> CommitteeGuardReport:
        evidence = evidence or {}
        modules = {}

        self._add(
            modules, "financial_health",
            evidence.get("financial_health"),
            score_keys=("confidence_adjusted_score", "score"),
            confidence_keys=("evidence_confidence", "confidence"),
            coverage_keys=("evidence_coverage", "coverage"),
        )
        self._add(modules, "accounting_quality", evidence.get("accounting_quality"))
        self._add(modules, "valuation", evidence.get("valuation"))
        self._add(modules, "event_intelligence", evidence.get("event_intelligence"))
        self._add(modules, "macro_regime", evidence.get("macro_regime"))
        self._add(modules, "advanced_market", evidence.get("advanced_market"))

        risk = self._dict(evidence.get("unified_risk"))
        risk_score = self._number(risk.get("risk_score"))
        risk_level = str(risk.get("risk_level") or "UNKNOWN").upper()
        hard_overrides = list(risk.get("hard_overrides") or [])

        if risk_score is not None:
            modules["unified_risk_quality"] = {
                "score": 100.0 - self._clip(risk_score),
                "confidence": self._percent(risk.get("confidence"), default=0.0),
                "coverage": self._percent(risk.get("coverage"), default=0.0),
            }

        weighted = 0.0
        denom = 0.0
        base_present = 0.0
        authority_num = 0.0

        module_scores = {}
        for name, item in modules.items():
            base = self.WEIGHTS[name]
            authority = (
                self._clip(item["confidence"]) / 100.0
                * self._clip(item["coverage"]) / 100.0
            )
            effective = base * authority
            weighted += item["score"] * effective
            denom += effective
            base_present += base
            authority_num += base * authority
            module_scores[name] = {
                "score": round(item["score"], 2),
                "confidence": round(item["confidence"], 2),
                "coverage": round(item["coverage"], 2),
                "authority": round(authority * 100.0, 2),
                "weight": base,
            }

        deterministic_score = weighted / denom if denom else 50.0
        module_coverage = base_present / sum(self.WEIGHTS.values()) * 100.0
        evidence_authority = (
            authority_num / base_present * 100.0 if base_present else 0.0
        )

        maximum_decision = "TOP_CANDIDATE"
        constraints = []
        governance_status = "PASS"

        # Deterministic risk is sovereign over the LLM.
        if hard_overrides:
            maximum_decision = "WATCH"
            governance_status = "RISK_CONSTRAINED"
            constraints.append(
                "Deterministic hard-risk override prevents promotion above WATCH."
            )

        if risk_level == "EXTREME":
            maximum_decision = self._stricter(maximum_decision, "WAIT")
            governance_status = "RISK_CONSTRAINED"
            constraints.append("EXTREME unified risk prevents promotion above WAIT.")
        elif risk_level == "VERY_HIGH":
            maximum_decision = self._stricter(maximum_decision, "WATCH")
            governance_status = "RISK_CONSTRAINED"
            constraints.append("VERY_HIGH unified risk prevents promotion above WATCH.")
        elif risk_level == "HIGH":
            maximum_decision = self._stricter(maximum_decision, "CANDIDATE")
            constraints.append("HIGH unified risk prevents TOP_CANDIDATE status.")

        # Weak evidence can never become high conviction merely because the LLM is eloquent.
        if module_coverage < 60.0:
            maximum_decision = self._stricter(maximum_decision, "WATCH")
            governance_status = "EVIDENCE_CONSTRAINED"
            constraints.append(
                f"Committee module coverage is only {module_coverage:.1f}%."
            )

        if evidence_authority < 45.0:
            maximum_decision = self._stricter(maximum_decision, "WATCH")
            governance_status = "EVIDENCE_CONSTRAINED"
            constraints.append(
                f"Weighted evidence authority is only {evidence_authority:.1f}%."
            )

        return CommitteeGuardReport(
            deterministic_score=round(self._clip(deterministic_score), 2),
            evidence_authority=round(evidence_authority, 2),
            module_coverage=round(module_coverage, 2),
            risk_score=round(risk_score, 2) if risk_score is not None else None,
            risk_level=risk_level,
            hard_overrides=hard_overrides,
            maximum_decision=maximum_decision,
            governance_status=governance_status,
            constraints=constraints,
            module_scores=module_scores,
        )

    def apply(
        self,
        llm_score: float,
        llm_decision: str,
        llm_confidence: float,
        integrity_score: float,
        guard: CommitteeGuardReport,
        deterministic_only: bool = False,
    ) -> dict:
        """V4.6: deterministic governance is sovereign.

        Nemotron output is retained for research/audit visibility only. It has
        zero score weight and zero decision authority. This keeps the old deep
        committee usable as a red-team/research layer without allowing provider
        behavior to alter Baby's reproducible ranking.
        """
        ds = self._clip(guard.deterministic_score)
        if ds >= 75:
            decision = "TOP_CANDIDATE"
        elif ds >= 62:
            decision = "CANDIDATE"
        elif ds >= 48:
            decision = "WATCH"
        elif ds >= 35:
            decision = "WAIT"
        else:
            decision = "AVOID"
        decision = self._cap_decision(decision, guard.maximum_decision)
        integrity = self._clip(self._number(integrity_score) or 0.0)
        return {
            "final_score": round(ds, 2),
            "llm_score": None,
            "llm_observed_score": round(self._clip(self._number(llm_score) or 0.0), 2) if not deterministic_only else None,
            "llm_weight": 0.0,
            "decision": decision,
            "confidence": round(guard.evidence_authority, 2),
            "confidence_ceiling": round(guard.evidence_authority, 2),
            "ai_role": "RESEARCH_RED_TEAM_ONLY",
            "ai_scoring_authority": 0.0,
            "ai_decision_authority": 0.0,
            "integrity_score": round(integrity, 2),
        }

    def _add(
        self, modules, name, raw,
        score_keys=("score",),
        confidence_keys=("confidence",),
        coverage_keys=("coverage",),
    ):
        d = self._dict(raw)
        if not d:
            return
        score = self._first(d, score_keys)
        if score is None:
            return
        modules[name] = {
            "score": self._clip(score),
            "confidence": self._percent(self._first(d, confidence_keys), default=0.0),
            "coverage": self._percent(self._first(d, coverage_keys), default=0.0),
        }

    @staticmethod
    def _dict(value):
        if isinstance(value, dict):
            return value
        if hasattr(value, "__dict__"):
            return dict(value.__dict__)
        return {}

    def _first(self, d, keys):
        for key in keys:
            if key in d and d[key] is not None:
                return self._number(d[key])
        return None

    @staticmethod
    def _number(value):
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _clip(value):
        return max(0.0, min(100.0, float(value)))

    def _percent(self, value, default=0.0):
        n = self._number(value)
        if n is None:
            return default
        # Some older evidence layers express confidence as 0..1.
        if 0.0 <= n <= 1.0:
            n *= 100.0
        return self._clip(n)

    def _stricter(self, current, proposed):
        return (
            proposed
            if self.DECISION_ORDER[proposed] < self.DECISION_ORDER[current]
            else current
        )

    def _cap_decision(self, decision, ceiling):
        if self.DECISION_ORDER[decision] > self.DECISION_ORDER[ceiling]:
            return ceiling
        return decision
