from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


@dataclass
class CrossSourceResult:
    metric: str
    primary_value: float | None
    secondary_value: float | None
    primary_period: str | None
    secondary_period: str | None
    period_status: str
    difference_pct: float | None
    difference_percentage_points: float | None
    status: str
    selected_value: float | None
    selected_source: str
    confidence: float
    note: str

    def to_dict(self):
        return asdict(self)


class CrossSourceValidator:
    """
    Raw statement metrics should be validated before ratios.

    Bands are deliberately conservative defaults:
      <=1%  strong agreement
      <=3%  agreement
      <=5%  minor difference
      <=10% review
      >10%  material disagreement

    Percentage/rate metrics are compared in percentage points.
    """

    RATE_METRICS = {
        "revenue_growth_yoy",
        "gross_margin",
        "operating_margin",
        "net_margin",
        "shares_change_yoy",
    }

    def validate(
        self,
        metric: str,
        primary_value: Any,
        secondary_value: Any,
        primary_period: str | None = None,
        secondary_period: str | None = None,
    ) -> CrossSourceResult:
        p = self._number(primary_value)
        s = self._number(secondary_value)

        period_status = self._period_status(
            primary_period,
            secondary_period,
        )

        if p is None and s is None:
            return self._result(
                metric, p, s, primary_period, secondary_period,
                period_status, None, None, "MISSING",
                None, "none", 0.0,
                "Neither source supplied a usable value.",
            )

        if p is None:
            return self._result(
                metric, p, s, primary_period, secondary_period,
                period_status, None, None, "SECONDARY_ONLY",
                s, "secondary", 0.55,
                "Primary SEC metric unavailable; secondary retained as fallback evidence.",
            )

        if s is None:
            return self._result(
                metric, p, s, primary_period, secondary_period,
                period_status, None, None, "PRIMARY_ONLY",
                p, "SEC_XBRL", 0.85,
                "Only normalized SEC primary-source value is available.",
            )

        if period_status == "MISMATCH":
            return self._result(
                metric, p, s, primary_period, secondary_period,
                period_status, None, None, "PERIOD_MISMATCH",
                p, "SEC_XBRL", 0.70,
                "Values were not treated as confirmation because periods differ.",
            )

        if metric in self.RATE_METRICS:
            pp = abs(p - s) * 100.0
            if pp <= 1:
                status, confidence = "STRONG_AGREEMENT", 0.98
            elif pp <= 3:
                status, confidence = "AGREEMENT", 0.94
            elif pp <= 5:
                status, confidence = "MINOR_DIFFERENCE", 0.85
            elif pp <= 10:
                status, confidence = "REVIEW", 0.65
            else:
                status, confidence = "MATERIAL_DISAGREEMENT", 0.35

            selected = p if status not in {"MATERIAL_DISAGREEMENT"} else None
            source = "SEC_XBRL" if selected is not None else "unresolved"

            return self._result(
                metric, p, s, primary_period, secondary_period,
                period_status, None, pp, status,
                selected, source, confidence,
                "Rate metric compared in percentage points.",
            )

        denominator = max(abs(p), abs(s), 1.0)
        diff_pct = abs(p - s) / denominator * 100.0

        if diff_pct <= 1:
            status, confidence = "STRONG_AGREEMENT", 0.99
        elif diff_pct <= 3:
            status, confidence = "AGREEMENT", 0.96
        elif diff_pct <= 5:
            status, confidence = "MINOR_DIFFERENCE", 0.88
        elif diff_pct <= 10:
            status, confidence = "REVIEW", 0.68
        else:
            status, confidence = "MATERIAL_DISAGREEMENT", 0.35

        selected = p if status != "MATERIAL_DISAGREEMENT" else None
        source = "SEC_XBRL" if selected is not None else "unresolved"

        return self._result(
            metric, p, s, primary_period, secondary_period,
            period_status, diff_pct, None, status,
            selected, source, confidence,
            "Raw financial metric compared after period check.",
        )

    @staticmethod
    def _period_status(primary, secondary):
        if not primary or not secondary:
            return "UNKNOWN"
        if primary == secondary:
            return "MATCH"
        return "MISMATCH"

    @staticmethod
    def _number(value):
        if value is None or isinstance(value, bool):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _result(*args):
        return CrossSourceResult(*args)
