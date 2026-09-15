from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


@dataclass
class ReconciledMetric:
    metric: str
    sec_value: float | None
    secondary_value: float | None
    selected_value: float | None
    selected_source: str
    status: str
    difference: float | None
    difference_pct_points: float | None
    note: str

    def to_dict(self):
        return asdict(self)


class FinancialReconciler:
    """
    SEC is primary only when Baby has a comparable normalized SEC metric.

    Yahoo/secondary data is not silently substituted when the two sources
    materially disagree. Disagreements become evidence.
    """

    PERCENT_METRICS = {
        "revenue_growth_yoy",
        "gross_margin",
        "operating_margin",
        "net_margin",
        "shares_change_yoy",
    }

    def reconcile(
        self,
        metric: str,
        sec_value: float | None,
        secondary_value: float | None,
        abs_tolerance: float | None = None,
    ) -> ReconciledMetric:
        if sec_value is None and secondary_value is None:
            return ReconciledMetric(
                metric, None, None, None,
                "none", "missing", None, None,
                "Metric unavailable from both sources.",
            )

        if sec_value is not None and secondary_value is None:
            return ReconciledMetric(
                metric, sec_value, None, sec_value,
                "SEC_XBRL", "sec_only", None, None,
                "Using normalized SEC primary-source value.",
            )

        if sec_value is None and secondary_value is not None:
            return ReconciledMetric(
                metric, None, secondary_value, secondary_value,
                "secondary_fallback", "secondary_only", None, None,
                "SEC comparable metric unavailable; secondary value retained as fallback.",
            )

        difference = sec_value - secondary_value

        if metric in self.PERCENT_METRICS:
            tolerance = (
                abs_tolerance
                if abs_tolerance is not None
                else 0.03
            )
            pp = abs(difference) * 100.0

            if abs(difference) <= tolerance:
                return ReconciledMetric(
                    metric,
                    sec_value,
                    secondary_value,
                    sec_value,
                    "SEC_XBRL",
                    "agreement",
                    difference,
                    pp,
                    "Sources are within reconciliation tolerance; SEC selected.",
                )

            return ReconciledMetric(
                metric,
                sec_value,
                secondary_value,
                None,
                "unresolved",
                "disagreement",
                difference,
                pp,
                "Material source disagreement. Baby must not silently choose a value.",
            )

        scale = max(
            abs(sec_value),
            abs(secondary_value),
            1.0,
        )
        relative_difference = abs(difference) / scale
        tolerance = (
            abs_tolerance
            if abs_tolerance is not None
            else 0.10
        )

        if relative_difference <= tolerance:
            return ReconciledMetric(
                metric,
                sec_value,
                secondary_value,
                sec_value,
                "SEC_XBRL",
                "agreement",
                difference,
                None,
                "Sources are within reconciliation tolerance; SEC selected.",
            )

        return ReconciledMetric(
            metric,
            sec_value,
            secondary_value,
            None,
            "unresolved",
            "disagreement",
            difference,
            None,
            "Material source disagreement. Baby must not silently choose a value.",
        )

    def reconcile_many(
        self,
        sec_metrics: dict[str, Any],
        secondary_metrics: dict[str, Any],
    ) -> dict[str, dict]:
        keys = sorted(
            set(sec_metrics)
            | set(secondary_metrics)
        )

        output = {}

        for key in keys:
            sec = self._number(
                sec_metrics.get(key)
            )
            secondary = self._number(
                secondary_metrics.get(key)
            )

            output[key] = self.reconcile(
                key,
                sec,
                secondary,
            ).to_dict()

        return output

    @staticmethod
    def _number(value):
        if value is None:
            return None
        if isinstance(value, bool):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
