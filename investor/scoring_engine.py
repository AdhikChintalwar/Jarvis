from __future__ import annotations

from investor.financial_evidence import (
    CANONICAL_FINANCIAL_EVIDENCE_METRICS,
    FinancialEvidenceContext,
)
from investor.models import (
    FundamentalMetrics,
    MarketMetrics,
    RiskLevel,
    RiskMetrics,
    ScoreComponent,
    Signal,
    StockScore,
    TechnicalMetrics,
)


class StockScoringEngine:
    def score(
        self,
        market: MarketMetrics,
        technical: TechnicalMetrics,
        fundamentals: FundamentalMetrics,
        risk: RiskMetrics,
        primary_financial: dict | None = None,
        accounting_quality=None,
        valuation=None,
    ) -> StockScore:
        components = [
            self._trend_score(technical),
            self._momentum_score(technical),
            self._volume_score(technical),
            self._fundamental_score(
                fundamentals,
                primary_financial=primary_financial,
            ),
            self._accounting_quality_score(accounting_quality),
            self._valuation_score(valuation),
            self._risk_score(risk),
        ]

        total_weight = sum(component.weight for component in components)
        overall = (
            sum(component.weighted_score for component in components)
            / total_weight
        )
        signal = self._signal(overall)

        strengths = []
        weaknesses = []
        for component in components:
            if component.score >= 70:
                strengths.append(component.explanation)
            elif component.score <= 40:
                weaknesses.append(component.explanation)

        if primary_financial:
            financial_summary = FinancialEvidenceContext(
                primary_financial
            ).summarize(CANONICAL_FINANCIAL_EVIDENCE_METRICS)
        else:
            financial_summary = {
                "confidence": 0.0,
                "coverage": 0.0,
                "gated": [],
            }

        component_confidence = {
            "trend": 0.90 if technical.trend_signal is not None else 0.0,
            "momentum": (
                0.90
                if (
                    technical.rsi_14 is not None
                    or technical.macd_histogram is not None
                )
                else 0.0
            ),
            "volume": 0.85 if technical.relative_volume is not None else 0.0,
            "fundamentals": (
                financial_summary["confidence"]
                if primary_financial
                else 0.50
            ),
            "accounting_quality": (accounting_quality.confidence / 100.0 if accounting_quality is not None else 0.0),
            "valuation": (valuation.confidence / 100.0 if valuation is not None else 0.0),
            "risk": 0.90 if risk.overall_risk is not None else 0.0,
        }

        confidence = (
            sum(
                component.weight
                * component_confidence.get(component.name, 0.0)
                for component in components
            )
            / total_weight
            * 100
        )

        return StockScore(
            overall_score=round(overall, 2),
            confidence=round(confidence, 2),
            signal=signal,
            components=components,
            strengths=strengths,
            weaknesses=weaknesses,
            financial_evidence_confidence=round(
                financial_summary["confidence"] * 100,
                2,
            ),
            financial_evidence_coverage=round(
                financial_summary["coverage"] * 100,
                2,
            ),
            gated_financial_metrics=list(financial_summary["gated"]),
        )

    def _trend_score(self, technical):
        mapping = {
            Signal.STRONG_BULLISH: 90,
            Signal.BULLISH: 75,
            Signal.NEUTRAL: 50,
            Signal.BEARISH: 30,
            Signal.STRONG_BEARISH: 15,
        }
        value = mapping[technical.trend_signal]
        return ScoreComponent(
            name="trend",
            score=value,
            weight=0.25,
            explanation=f"Trend is {technical.trend_signal.value}.",
        )

    def _momentum_score(self, technical):
        rsi = technical.rsi_14
        score = 50

        if rsi is not None:
            if 50 <= rsi <= 65:
                score += 15
            elif 65 < rsi <= 72:
                score += 5
            elif rsi > 75:
                score -= 15
            elif 35 <= rsi < 50:
                score -= 5
            elif rsi < 30:
                score -= 10

        if technical.macd_histogram is not None:
            if technical.macd_histogram > 0:
                score += 10
            else:
                score -= 10

        score = max(0, min(100, score))
        return ScoreComponent(
            name="momentum",
            score=score,
            weight=0.20,
            explanation=f"Momentum score based on RSI and MACD: {score:.0f}/100.",
        )

    def _volume_score(self, technical):
        relative_volume = technical.relative_volume

        if relative_volume is None:
            score = 50
        elif relative_volume >= 3:
            score = 85
        elif relative_volume >= 2:
            score = 75
        elif relative_volume >= 1.25:
            score = 65
        elif relative_volume >= 0.8:
            score = 50
        else:
            score = 35

        explanation = (
            f"Relative volume is {relative_volume:.2f}x."
            if relative_volume is not None
            else "Relative volume unavailable."
        )
        return ScoreComponent(
            name="volume",
            score=score,
            weight=0.15,
            explanation=explanation,
        )

    def _fundamental_score(
        self,
        fundamentals,
        primary_financial=None,
    ):
        evidence = FinancialEvidenceContext(primary_financial)
        score = 50.0
        used_authorities = []

        def authority(metric_name):
            if not primary_financial:
                return 1.0
            metric = evidence.metric(metric_name)
            return metric.authority if metric.available else 0.0

        growth = fundamentals.revenue_growth
        weight = authority("revenue_growth_yoy")
        if growth is not None and weight > 0:
            used_authorities.append(weight)
            if growth > 0.20:
                score += 15 * weight
            elif growth > 0.05:
                score += 8 * weight
            elif growth < 0:
                score -= 15 * weight

        margin = fundamentals.profit_margin
        weight = authority("net_margin")
        if margin is not None and weight > 0:
            used_authorities.append(weight)
            if margin > 0.20:
                score += 12 * weight
            elif margin > 0:
                score += 5 * weight
            else:
                score -= 10 * weight

        free_cash_flow = fundamentals.free_cash_flow
        weight = authority("free_cash_flow")
        if free_cash_flow is not None and weight > 0:
            used_authorities.append(weight)
            score += (8 if free_cash_flow > 0 else -8) * weight

        score = max(0, min(100, score))
        mean_authority = (
            sum(used_authorities) / len(used_authorities)
            if used_authorities
            else 0.0
        )

        return ScoreComponent(
            name="fundamentals",
            score=score,
            weight=0.25,
            explanation=(
                f"Fundamental quality score: {score:.0f}/100 using "
                f"{len(used_authorities)} authority-gated factors "
                f"(mean evidence authority {mean_authority:.0%})."
            ),
        )

    def _accounting_quality_score(self, accounting_quality):
        if accounting_quality is None:
            score, explanation = 50.0, "Accounting quality unavailable."
        else:
            score = accounting_quality.score
            explanation = f"Accounting quality score: {score:.0f}/100 with {accounting_quality.coverage:.0f}% evidence coverage."
        return ScoreComponent(name="accounting_quality", score=score, weight=0.10, explanation=explanation)

    def _valuation_score(self, valuation):
        if valuation is None:
            score, explanation = 50.0, "Valuation intelligence unavailable."
        else:
            score = valuation.score
            explanation = (
                f"Valuation score: {score:.0f}/100 with "
                f"{valuation.coverage:.0f}% evidence coverage."
            )
        return ScoreComponent(
            name="valuation",
            score=score,
            weight=0.15,
            explanation=explanation,
        )

    def _risk_score(self, risk):
        mapping = {
            RiskLevel.VERY_LOW: 90,
            RiskLevel.LOW: 75,
            RiskLevel.MODERATE: 55,
            RiskLevel.HIGH: 30,
            RiskLevel.VERY_HIGH: 10,
        }
        value = mapping[risk.overall_risk]
        return ScoreComponent(
            name="risk",
            score=value,
            weight=0.15,
            explanation=f"Overall risk is {risk.overall_risk.value}.",
        )

    def _signal(self, score):
        if score >= 80:
            return Signal.STRONG_BULLISH
        if score >= 65:
            return Signal.BULLISH
        if score >= 45:
            return Signal.NEUTRAL
        if score >= 30:
            return Signal.BEARISH
        return Signal.STRONG_BEARISH
