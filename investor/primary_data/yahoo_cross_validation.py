from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

from .cross_source_validator import CrossSourceValidator
from .yahoo_financial_adapter import YahooFinancialAdapter


@dataclass
class ValidationSummary:
    metrics: dict
    strong_agreements: int
    agreements: int
    reviews: int
    disagreements: int
    unresolved: int
    confidence: float

    def to_dict(self):
        return asdict(self)


class YahooCrossValidationEngine:
    """
    Secondary validation layer.

    Yahoo is supporting evidence only. It never silently overwrites a
    valid SEC value.
    """

    def __init__(self):
        self.validator = CrossSourceValidator()
        self.adapter = YahooFinancialAdapter()

    def validate(
        self,
        sec_metrics: dict,
        yahoo_info: dict[str, Any],
        *,
        sec_periods: dict[str, str | None] | None = None,
        yahoo_periods: dict[str, str | None] | None = None,
    ) -> ValidationSummary:
        yahoo = self.adapter.normalize(yahoo_info)
        sec_periods = sec_periods or {}
        yahoo_periods = yahoo_periods or {}

        metrics = {}
        counts = {
            "STRONG_AGREEMENT": 0,
            "AGREEMENT": 0,
            "MINOR_DIFFERENCE": 0,
            "REVIEW": 0,
            "MATERIAL_DISAGREEMENT": 0,
            "MISSING": 0,
            "PRIMARY_ONLY": 0,
            "SECONDARY_ONLY": 0,
            "PERIOD_MISMATCH": 0,
        }

        keys = [
            "revenue",
            "revenue_growth_yoy",
            "gross_margin",
            "operating_margin",
            "net_margin",
            "operating_cash_flow",
            "free_cash_flow",
            "cash",
            "debt",
        ]

        confidence_values = []

        for metric in keys:
            result = self.validator.validate(
                metric=metric,
                primary_value=sec_metrics.get(metric),
                secondary_value=yahoo.get(metric),
                primary_period=sec_periods.get(metric),
                secondary_period=yahoo_periods.get(metric),
            )

            metrics[metric] = result.to_dict()
            counts[result.status] = counts.get(result.status, 0) + 1

            if result.status not in {
                "MISSING",
                "SECONDARY_ONLY",
                "PERIOD_MISMATCH",
            }:
                confidence_values.append(result.confidence)

        confidence = (
            sum(confidence_values) / len(confidence_values)
            if confidence_values else 0.0
        )

        return ValidationSummary(
            metrics=metrics,
            strong_agreements=counts["STRONG_AGREEMENT"],
            agreements=(
                counts["AGREEMENT"]
                + counts["MINOR_DIFFERENCE"]
            ),
            reviews=(
                counts["REVIEW"]
                + counts["PERIOD_MISMATCH"]
            ),
            disagreements=counts["MATERIAL_DISAGREEMENT"],
            unresolved=(
                counts["MISSING"]
                + counts["SECONDARY_ONLY"]
            ),
            confidence=confidence,
        )
