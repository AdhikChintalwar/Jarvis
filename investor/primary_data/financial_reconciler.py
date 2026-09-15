from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import date


@dataclass
class ReconciliationResult:
    metric: str
    primary_value: float | None
    secondary_value: float | None
    primary_period: str | None
    secondary_period: str | None
    period_status: str
    difference: float | None
    status: str
    confidence: float
    selected_value: float | None
    selected_source: str
    reason: str
    semantic_status: str | None = None
    semantic_evidence: dict | None = None

    def to_dict(self):
        return asdict(self)


class PeriodAwareFinancialReconciler:
    RATE_METRICS = {
        "revenue_growth_yoy",
        "gross_margin",
        "operating_margin",
        "net_margin",
    }

    def reconcile(
        self,
        metric,
        primary_value,
        primary_period,
        secondary_value,
        secondary_period,
        semantic_assessment=None,
    ):
        if primary_value is None and secondary_value is None:
            return self._make(
                metric, primary_value, secondary_value,
                primary_period, secondary_period,
                "UNKNOWN", None, "MISSING", 0.0, None, "none",
                "Neither source supplied a usable value.",
                semantic_assessment,
            )

        if primary_value is not None and secondary_value is None:
            return self._make(
                metric, primary_value, None,
                primary_period, secondary_period,
                "UNKNOWN", None, "PRIMARY_ONLY", 0.85,
                primary_value, "SEC_XBRL",
                "SEC value available; secondary value unavailable.",
                semantic_assessment,
            )

        if primary_value is None and secondary_value is not None:
            return self._make(
                metric, None, secondary_value,
                primary_period, secondary_period,
                "UNKNOWN", None, "SECONDARY_ONLY", 0.55,
                secondary_value, "YAHOO_FINANCE",
                "SEC unavailable; Yahoo fallback only.",
                semantic_assessment,
            )

        period_status = self._period_status(primary_period, secondary_period)
        difference = self._difference(
            metric, float(primary_value), float(secondary_value)
        )

        if period_status == "MISMATCH":
            return self._make(
                metric, primary_value, secondary_value,
                primary_period, secondary_period,
                period_status, difference, "PERIOD_MISMATCH", 0.70,
                primary_value, "SEC_XBRL",
                "Fiscal periods differ; secondary source cannot confirm SEC.",
                semantic_assessment,
            )

        if semantic_assessment is not None and not semantic_assessment.comparable:
            return self._make(
                metric, primary_value, secondary_value,
                primary_period, secondary_period,
                period_status, difference,
                semantic_assessment.status,
                semantic_assessment.confidence,
                primary_value, "SEC_XBRL",
                semantic_assessment.reason,
                semantic_assessment,
            )

        if period_status == "UNKNOWN":
            status = (
                "VALUE_AGREEMENT_PERIOD_UNVERIFIED"
                if self._is_agreement(metric, difference)
                else "VALUE_DISAGREEMENT_PERIOD_UNVERIFIED"
            )
            return self._make(
                metric, primary_value, secondary_value,
                primary_period, secondary_period,
                period_status, difference, status, 0.72,
                primary_value, "SEC_XBRL",
                "Value comparison exists but fiscal period is unverified.",
                semantic_assessment,
            )

        status, confidence = self._agreement_band(metric, difference)
        selected = primary_value
        source = "SEC_XBRL"

        if status == "MATERIAL_DISAGREEMENT":
            selected = None
            source = "unresolved"

        return self._make(
            metric, primary_value, secondary_value,
            primary_period, secondary_period,
            period_status, difference, status, confidence,
            selected, source,
            "SEC remains primary; secondary source is validation evidence.",
            semantic_assessment,
        )

    @staticmethod
    def _period_status(primary, secondary):
        if not primary or not secondary:
            return "UNKNOWN"
        try:
            a = date.fromisoformat(primary)
            b = date.fromisoformat(secondary)
        except ValueError:
            return "UNKNOWN"
        gap = abs((a - b).days)
        if gap <= 7:
            return "MATCH"
        if gap <= 45:
            return "APPROXIMATE_MATCH"
        return "MISMATCH"

    def _difference(self, metric, primary, secondary):
        if metric in self.RATE_METRICS:
            return abs(primary - secondary)
        denom = max(abs(primary), abs(secondary), 1.0)
        return abs(primary - secondary) / denom

    def _agreement_band(self, metric, difference):
        if metric in self.RATE_METRICS:
            if difference <= .005: return "STRONG_AGREEMENT", .97
            if difference <= .015: return "AGREEMENT", .94
            if difference <= .03: return "MINOR_DIFFERENCE", .88
            if difference <= .05: return "REVIEW", .72
            return "MATERIAL_DISAGREEMENT", .25
        if difference <= .01: return "STRONG_AGREEMENT", .97
        if difference <= .03: return "AGREEMENT", .94
        if difference <= .05: return "MINOR_DIFFERENCE", .88
        if difference <= .10: return "REVIEW", .72
        return "MATERIAL_DISAGREEMENT", .25

    def _is_agreement(self, metric, difference):
        if difference is None:
            return False
        return difference <= (.03 if metric in self.RATE_METRICS else .05)

    @staticmethod
    def _make(
        metric, primary_value, secondary_value,
        primary_period, secondary_period,
        period_status, difference, status, confidence,
        selected_value, selected_source, reason, semantic,
    ):
        return ReconciliationResult(
            metric=metric,
            primary_value=primary_value,
            secondary_value=secondary_value,
            primary_period=primary_period,
            secondary_period=secondary_period,
            period_status=period_status,
            difference=difference,
            status=status,
            confidence=confidence,
            selected_value=selected_value,
            selected_source=selected_source,
            reason=reason,
            semantic_status=(semantic.status if semantic else None),
            semantic_evidence=(semantic.to_dict() if semantic else None),
        )
