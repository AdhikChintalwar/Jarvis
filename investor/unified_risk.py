from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
import math


@dataclass
class RiskDimension:
    name: str
    score: float | None = None          # 0 = low risk, 100 = extreme risk
    confidence: float = 0.0
    coverage: float = 0.0
    state: str = "unknown"
    evidence: list[str] = field(default_factory=list)
    unknowns: list[str] = field(default_factory=list)
    hard_override: bool = False


@dataclass
class UnifiedRiskReport:
    risk_score: float = 50.0
    risk_level: str = "UNKNOWN"
    confidence: float = 0.0
    coverage: float = 0.0

    dimensions: dict = field(default_factory=dict)
    hard_overrides: list[str] = field(default_factory=list)
    risk_flags: list[str] = field(default_factory=list)
    protective_factors: list[str] = field(default_factory=list)
    unknowns: list[str] = field(default_factory=list)

    position_risk_multiplier: float = 1.0
    generated_at: str = ""
    schema_version: str = "4.2"


class UnifiedRiskEngine:
    """
    Deterministic risk aggregation.

    Design:
    - Risk is separate from investment quality.
    - Missing evidence is UNKNOWN, not automatically risky.
    - Dimensions are confidence-weighted.
    - Severe deterministic observations can create hard overrides.
    - position_risk_multiplier is a future sizing input, not an order instruction.
    """

    WEIGHTS = {
        "financial": 0.18,
        "accounting": 0.14,
        "valuation": 0.10,
        "market_volatility": 0.20,
        "liquidity": 0.14,
        "event_sec": 0.12,
        "macro_market": 0.12,
    }

    def analyze(self, report: dict) -> UnifiedRiskReport:
        dims = {
            "financial": self._financial(report),
            "accounting": self._accounting(report),
            "valuation": self._valuation(report),
            "market_volatility": self._market_volatility(report),
            "liquidity": self._liquidity(report),
            "event_sec": self._event_sec(report),
            "macro_market": self._macro_market(report),
        }

        weighted_num = 0.0
        weighted_den = 0.0
        available_weight = 0.0

        for name, dim in dims.items():
            if dim.score is None:
                continue
            base_weight = self.WEIGHTS[name]
            authority = max(0.0, min(1.0, dim.confidence / 100.0))
            effective = base_weight * authority
            weighted_num += dim.score * effective
            weighted_den += effective
            available_weight += base_weight

        aggregate = weighted_num / weighted_den if weighted_den else 50.0

        hard_overrides = []
        for dim in dims.values():
            if dim.hard_override:
                hard_overrides.extend(dim.evidence)

        # Hard overrides impose a risk floor; they do not invent a precise score.
        if hard_overrides:
            aggregate = max(aggregate, 80.0)

        aggregate = round(max(0.0, min(100.0, aggregate)), 2)

        if aggregate >= 85:
            level = "EXTREME"
        elif aggregate >= 70:
            level = "VERY_HIGH"
        elif aggregate >= 55:
            level = "HIGH"
        elif aggregate >= 40:
            level = "MODERATE"
        else:
            level = "LOW"

        confidence_parts = [
            d.confidence for d in dims.values() if d.score is not None
        ]
        confidence = (
            sum(confidence_parts) / len(confidence_parts)
            if confidence_parts else 0.0
        )
        coverage = available_weight / sum(self.WEIGHTS.values()) * 100.0

        flags, protective, unknowns = [], [], []
        for dim in dims.values():
            unknowns.extend(dim.unknowns)
            if dim.score is None:
                continue
            if dim.score >= 70:
                flags.extend(dim.evidence)
            elif dim.score <= 30:
                protective.extend(dim.evidence)

        # Conservative future sizing scalar. It does not place or recommend trades.
        if level == "EXTREME":
            multiplier = 0.25
        elif level == "VERY_HIGH":
            multiplier = 0.40
        elif level == "HIGH":
            multiplier = 0.60
        elif level == "MODERATE":
            multiplier = 0.80
        else:
            multiplier = 1.00

        return UnifiedRiskReport(
            risk_score=aggregate,
            risk_level=level,
            confidence=round(confidence, 2),
            coverage=round(coverage, 2),
            dimensions={k: asdict(v) for k, v in dims.items()},
            hard_overrides=self._unique(hard_overrides),
            risk_flags=self._unique(flags),
            protective_factors=self._unique(protective),
            unknowns=self._unique(unknowns),
            position_risk_multiplier=multiplier,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

    def _financial(self, r):
        h = self._obj(r.get("financial_health"))
        if not h:
            return self._unknown("financial", "financial_health")

        quality = self._num(h.get("quality_score"))
        if quality is None:
            # Compatibility with earlier object naming.
            quality = self._num(h.get("score"))

        conf = self._first_pct(
            h,
            "evidence_confidence",
            "confidence",
            "financial_confidence",
            "primary_financial_confidence",
        )
        cov = self._first_pct(
            h,
            "evidence_coverage",
            "coverage",
            "financial_coverage",
        )

        if quality is None:
            return self._unknown("financial", "financial_quality_score")

        risk = 100.0 - quality
        evidence = [f"Financial-health quality score={quality:.2f}."]
        return self._dimension("financial", risk, conf, cov, evidence)

    def _accounting(self, r):
        a = self._obj(r.get("accounting_quality"))
        if not a:
            return self._unknown("accounting", "accounting_quality")

        quality = self._first_num(a, "score", "quality_score", "accounting_score")
        conf = self._pct(a.get("confidence"))
        cov = self._pct(a.get("coverage"))

        if quality is None:
            return self._unknown("accounting", "accounting_quality_score")

        risk = 100.0 - quality
        evidence = [f"Accounting-quality score={quality:.2f}."]
        return self._dimension("accounting", risk, conf, cov, evidence)

    def _valuation(self, r):
        v = self._obj(r.get("valuation"))
        if not v:
            return self._unknown("valuation", "valuation")

        score = self._first_num(v, "score", "valuation_score")
        conf = self._pct(v.get("confidence"))
        cov = self._pct(v.get("coverage"))

        if score is None:
            return self._unknown("valuation", "valuation_score")

        # Valuation risk is deliberately bounded. Expensive != unsafe in the
        # same sense as insolvency, illiquidity, or extreme volatility.
        risk = max(20.0, min(80.0, 100.0 - score))
        evidence = [f"Valuation score={score:.2f}."]
        return self._dimension("valuation", risk, conf, cov, evidence)

    def _market_volatility(self, r):
        m = self._obj(r.get("advanced_market"))
        if not m:
            return self._unknown("market_volatility", "advanced_market")

        signals = m.get("signals") or {}
        vol = self._num((signals.get("realized_volatility_20d") or {}).get("value"))
        conf = self._pct((signals.get("realized_volatility_20d") or {}).get("confidence"))
        if conf <= 1:
            conf *= 100.0

        if vol is None:
            return self._unknown("market_volatility", "realized_volatility_20d")

        if vol >= 120:
            risk = 100
        elif vol >= 80:
            risk = 92
        elif vol >= 60:
            risk = 80
        elif vol >= 45:
            risk = 68
        elif vol >= 30:
            risk = 52
        elif vol >= 20:
            risk = 35
        else:
            risk = 22

        hard = vol >= 90
        evidence = [f"20D annualized realized volatility={vol:.2f}%."]
        if hard:
            evidence.append("Extreme realized-volatility hard override triggered.")

        return self._dimension(
            "market_volatility", risk, conf or 70.0, 100.0,
            evidence, hard_override=hard
        )

    def _liquidity(self, r):
        # Use existing market-data fields where available. Dollar volume is
        # preferred; relative volume is NOT liquidity.
        market = self._obj(r.get("market_data"))
        liquidity_evidence = self._obj(r.get("liquidity_evidence"))

        avg_dollar = self._first_num(
            liquidity_evidence,
            "average_dollar_volume_20d",
        )
        source = liquidity_evidence.get("source")
        as_of = liquidity_evidence.get("as_of")

        # Compatibility fallback only. Deterministic history-derived ADV20 is
        # preferred and supplied by StockAnalyzer in V4.2.1.
        if avg_dollar is None:
            avg_dollar = self._first_num(
                market, "average_dollar_volume_20d", "avg_dollar_volume_20d",
                "average_dollar_volume", "avg_dollar_volume"
            )
            source = source or "market_data fallback"

        avg_volume = self._first_num(
            market, "average_volume_20d", "avg_volume_20d", "average_volume"
        )
        price = self._first_num(market, "price", "current_price", "close")

        if avg_dollar is None and avg_volume is not None and price is not None:
            avg_dollar = avg_volume * price
            source = source or "market_data price×volume fallback"

        if avg_dollar is None:
            return self._unknown("liquidity", "average_dollar_volume_20d")

        if avg_dollar < 1_000_000:
            risk = 95
            hard = True
        elif avg_dollar < 5_000_000:
            risk = 82
            hard = False
        elif avg_dollar < 20_000_000:
            risk = 65
            hard = False
        elif avg_dollar < 100_000_000:
            risk = 42
            hard = False
        else:
            risk = 20
            hard = False

        evidence = [f"20D average dollar volume≈${avg_dollar:,.0f}."]
        if source:
            evidence.append(f"Liquidity source={source}.")
        if as_of:
            evidence.append(f"Liquidity as-of={as_of}.")
        if hard:
            evidence.append("Severe liquidity hard override triggered.")

        return self._dimension(
            "liquidity", risk, 65.0, 100.0, evidence, hard_override=hard
        )

    def _event_sec(self, r):
        e = self._obj(r.get("event_intelligence"))
        if not e:
            # compatibility with likely prior report keys
            e = self._obj(r.get("catalyst_intelligence"))
        if not e:
            return self._unknown("event_sec", "event_intelligence")

        score = self._first_num(e, "score", "event_score")
        conf = self._pct(e.get("confidence"))
        cov = self._pct(e.get("coverage"))

        # Event score in the current system is centered around 50.
        # Negative actionable SEC events should also be visible in risks.
        risks = e.get("risks") or []
        if score is None:
            if risks:
                score = 35.0
            else:
                return self._unknown("event_sec", "event_score")

        risk = max(0.0, min(100.0, 100.0 - score))
        evidence = [f"Event-intelligence score={score:.2f}."]
        evidence.extend(str(x) for x in risks[:3])

        # Do NOT hard-override on registration/mention-only events.
        actionable_text = " ".join(evidence).lower()
        hard = any(
            token in actionable_text
            for token in ("going concern", "completed transaction")
        ) and risk >= 75

        return self._dimension("event_sec", risk, conf, cov, evidence, hard_override=hard)

    def _macro_market(self, r):
        macro = self._obj(r.get("macro_regime"))
        market = self._obj(r.get("advanced_market"))

        parts = []
        confs = []
        evidence = []

        if macro:
            score = self._num(macro.get("score"))
            if score is not None:
                parts.append(100.0 - score)
                confs.append(self._pct(macro.get("confidence")))
                evidence.append(f"Macro regime={macro.get('regime')} score={score:.2f}.")

        if market:
            score = self._num(market.get("score"))
            if score is not None:
                parts.append(100.0 - score)
                confs.append(self._pct(market.get("confidence")))
                evidence.append(
                    f"Advanced market structure={market.get('market_structure')} score={score:.2f}."
                )

        if not parts:
            return self._unknown("macro_market", "macro_market_context")

        risk = sum(parts) / len(parts)
        conf = sum(confs) / len(confs) if confs else 0.0
        coverage = 100.0 if len(parts) == 2 else 50.0
        return self._dimension("macro_market", risk, conf, coverage, evidence)

    def _dimension(self, name, score, confidence, coverage, evidence, hard_override=False):
        score = max(0.0, min(100.0, float(score)))
        if score >= 85:
            state = "extreme"
        elif score >= 70:
            state = "very_high"
        elif score >= 55:
            state = "high"
        elif score >= 40:
            state = "moderate"
        else:
            state = "low"

        return RiskDimension(
            name=name,
            score=round(score, 2),
            confidence=round(max(0.0, min(100.0, confidence)), 2),
            coverage=round(max(0.0, min(100.0, coverage)), 2),
            state=state,
            evidence=evidence,
            hard_override=hard_override,
        )

    @staticmethod
    def _unknown(name, field):
        return RiskDimension(
            name=name, score=None, confidence=0.0, coverage=0.0,
            state="unknown", unknowns=[field]
        )

    @staticmethod
    def _obj(value):
        if value is None:
            return {}
        if isinstance(value, dict):
            return value
        try:
            return vars(value)
        except Exception:
            return {}

    @staticmethod
    def _num(value):
        try:
            x = float(value)
            return x if math.isfinite(x) else None
        except Exception:
            return None

    def _first_num(self, obj, *keys):
        for key in keys:
            x = self._num(obj.get(key))
            if x is not None:
                return x
        return None

    def _pct(self, value):
        x = self._num(value)
        if x is None:
            return 0.0
        if 0 <= x <= 1:
            x *= 100.0
        return max(0.0, min(100.0, x))

    def _first_pct(self, obj, *keys):
        for key in keys:
            if key not in obj:
                continue
            x = self._num(obj.get(key))
            if x is not None:
                return self._pct(x)
        return 0.0

    @staticmethod
    def _unique(items):
        seen, out = set(), []
        for x in items:
            if not x or x in seen:
                continue
            seen.add(x)
            out.append(x)
        return out
