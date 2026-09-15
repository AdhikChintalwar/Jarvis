from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .financial_statements import MetricSeries
from .fiscal_period_resolver import FiscalPeriodResolver


@dataclass
class FinancialTrendReport:
    metrics: dict
    warnings: list[str]
    diagnostics: dict

    def to_dict(self):
        return {
            "metrics": self.metrics,
            "warnings": self.warnings,
            "diagnostics": self.diagnostics,
        }


class FinancialTrendEngine:
    def __init__(self):
        self.periods = FiscalPeriodResolver()

    def analyze(self, statements: dict[str, MetricSeries]):
        m, warnings, diagnostics = {}, [], {}

        revenue = statements["revenue"]
        revenue_resolved = self.periods.resolve_latest_annual(
            revenue.annual
        )
        revenue_anchor = (
            revenue_resolved.fact.end
            if revenue_resolved.fact else None
        )

        m["revenue"] = (
            revenue_resolved.fact.value
            if revenue_resolved.fact
            and revenue.calculation_allowed
            else None
        )
        diagnostics["revenue_period"] = revenue_resolved.to_dict()

        m["revenue_growth_yoy"] = self._annual_yoy(revenue)
        m["revenue_cagr_3y"] = self._annual_cagr(revenue, 3)

        gross_margin, gross_diag = self._margin(
            statements["gross_profit"],
            revenue,
            revenue_anchor,
        )

        if gross_margin is None:
            cost_ratio, cost_diag = self._margin(
                statements["cost_of_revenue"],
                revenue,
                revenue_anchor,
            )
            if cost_ratio is not None:
                gross_margin = 1.0 - cost_ratio
                gross_diag = {
                    "status": "derived_from_cost_of_revenue",
                    "confidence": cost_diag.get("confidence", 0.0),
                    "period": cost_diag.get("period"),
                    "source_detail": cost_diag,
                }

        m["gross_margin"] = gross_margin
        diagnostics["gross_margin"] = gross_diag

        m["operating_margin"], diagnostics["operating_margin"] = self._margin(
            statements["operating_income"],
            revenue,
            revenue_anchor,
        )
        m["net_margin"], diagnostics["net_margin"] = self._margin(
            statements["net_income"],
            revenue,
            revenue_anchor,
        )

        m["operating_income"] = self._annual_value_near_anchor(
            statements["operating_income"],
            revenue_anchor,
        )
        m["net_income"] = self._annual_value_near_anchor(
            statements["net_income"],
            revenue_anchor,
        )

        ocf = self._annual_value_near_anchor(
            statements["operating_cash_flow"],
            revenue_anchor,
        )
        capex = self._annual_value_near_anchor(
            statements["capex"],
            revenue_anchor,
        )

        m["operating_cash_flow"] = ocf
        m["capex"] = capex
        m["free_cash_flow"] = (
            ocf - abs(capex)
            if ocf is not None and capex is not None
            else None
        )

        cash = self._latest_instant(statements["cash"])
        short_inv = self._latest_instant(
            statements["short_term_investments"]
        )
        debt_current = self._latest_instant(
            statements["debt_current"]
        ) or 0.0
        debt_noncurrent = self._latest_instant(
            statements["debt_noncurrent"]
        ) or 0.0
        debt = debt_current + debt_noncurrent

        m["cash"] = cash
        m["short_term_investments"] = short_inv
        m["cash_plus_short_term_investments"] = (
            (cash or 0.0) + (short_inv or 0.0)
            if cash is not None or short_inv is not None
            else None
        )
        m["debt"] = debt
        m["cash_to_debt"] = (
            cash / debt if cash is not None and debt > 0 else None
        )

        liquid = m["cash_plus_short_term_investments"]
        m["liquid_assets_to_debt"] = (
            liquid / debt if liquid is not None and debt > 0 else None
        )

        share_change, share_diag = self._safe_shares_yoy(
            statements["shares_outstanding"],
            statements["weighted_average_diluted_shares"],
        )
        m["shares_change_yoy"] = share_change
        diagnostics["shares_change_yoy"] = share_diag

        if m["free_cash_flow"] is not None and m["free_cash_flow"] < 0:
            warnings.append("Negative SEC-derived free cash flow.")

        if share_change is not None and share_change > 0.10:
            warnings.append(
                "Validated comparable share-count evidence indicates "
                "shares increased more than 10% year over year."
            )

        return FinancialTrendReport(m, warnings, diagnostics)

    def _margin(self, numerator, denominator, anchor_end):
        if (
            not numerator.calculation_allowed
            or not denominator.calculation_allowed
        ):
            return None, {
                "status": "semantic_rejection",
                "confidence": 0.0,
                "reason": (
                    numerator.semantic_note
                    if not numerator.calculation_allowed
                    else denominator.semantic_note
                ),
            }

        num, den = self.periods.resolve_same_period(
            numerator.annual,
            denominator.annual,
            anchor_end=anchor_end,
        )

        if not num.fact or not den.fact or not den.fact.value:
            return None, {
                "status": "period_unresolved",
                "confidence": 0.0,
                "anchor_end": anchor_end,
            }

        return (
            num.fact.value / den.fact.value,
            {
                "status": num.status,
                "confidence": min(
                    num.confidence,
                    den.confidence,
                    numerator.semantic_confidence,
                    denominator.semantic_confidence,
                ),
                "period": {
                    "start": num.fact.start,
                    "end": num.fact.end,
                },
                "anchor_end": anchor_end,
                "numerator_concept": numerator.concept,
                "denominator_concept": denominator.concept,
            },
        )

    def _annual_value_near_anchor(self, series, anchor_end):
        if not series.calculation_allowed:
            return None

        resolved = self.periods.resolve_latest_annual(series.annual)
        if not resolved.fact:
            return None

        if not anchor_end:
            return resolved.fact.value

        try:
            gap = abs(
                (
                    date.fromisoformat(resolved.fact.end)
                    - date.fromisoformat(anchor_end)
                ).days
            )
        except ValueError:
            return None

        return resolved.fact.value if gap <= 45 else None

    @staticmethod
    def _latest_instant(series):
        if not series.instantaneous:
            return None

        valid = [
            x for x in series.instantaneous
            if x.value is not None
        ]

        return valid[-1].value if valid else None

    def _annual_yoy(self, series):
        if not series.calculation_allowed:
            return None

        latest = self.periods.resolve_latest_annual(series.annual).fact
        if not latest:
            return None

        latest_end = date.fromisoformat(latest.end)
        candidates = []

        for prior in series.annual:
            if prior is latest or prior.value == 0:
                continue

            gap = (
                latest_end
                - date.fromisoformat(prior.end)
            ).days

            if 300 <= gap <= 430:
                candidates.append(
                    (abs(gap - 365), prior)
                )

        if not candidates:
            return None

        prior = min(candidates, key=lambda x: x[0])[1]
        return latest.value / prior.value - 1.0

    def _annual_cagr(self, series, years):
        if not series.calculation_allowed:
            return None

        latest = self.periods.resolve_latest_annual(series.annual).fact
        if not latest:
            return None

        latest_end = date.fromisoformat(latest.end)
        target = 365 * years
        candidates = []

        for prior in series.annual:
            if prior is latest or prior.value <= 0:
                continue

            gap = (
                latest_end
                - date.fromisoformat(prior.end)
            ).days

            if target - 100 <= gap <= target + 140:
                candidates.append(
                    (abs(gap - target), prior, gap)
                )

        if not candidates or latest.value < 0:
            return None

        _, prior, gap = min(candidates, key=lambda x: x[0])
        actual_years = gap / 365.25

        return (
            latest.value / prior.value
        ) ** (1.0 / actual_years) - 1.0

    def _safe_shares_yoy(self, shares, diluted):
        rows = [
            x for x in shares.instantaneous
            if x.value is not None and x.value > 0
        ]

        if len(rows) < 2:
            return None, {
                "status": "insufficient_positive_history",
                "selected_concept": shares.concept,
                "latest_economic_date": shares.latest_economic_date,
            }

        latest = rows[-1]
        latest_date = date.fromisoformat(latest.end)
        candidates = []

        for prior in rows[:-1]:
            if (
                prior.unit != latest.unit
                or prior.concept != latest.concept
                or prior.value <= 0
            ):
                continue

            gap = (
                latest_date
                - date.fromisoformat(prior.end)
            ).days

            if 300 <= gap <= 430:
                candidates.append(
                    (abs(gap - 365), prior, gap)
                )

        if not candidates:
            return None, {
                "status": "no_comparable_prior_period",
                "selected_concept": shares.concept,
                "latest_date": latest.end,
            }

        _, prior, gap = min(candidates, key=lambda x: x[0])
        change = latest.value / prior.value - 1.0

        diagnostic = {
            "status": "ok",
            "latest_date": latest.end,
            "latest_value": latest.value,
            "prior_date": prior.end,
            "prior_value": prior.value,
            "days_apart": gap,
            "concept": latest.concept,
            "unit": latest.unit,
            "raw_change": change,
            "series_quality": shares.series_quality,
        }

        if abs(change) > 1.0:
            diluted_change = self._diluted_yoy(diluted)
            diagnostic["weighted_average_diluted_shares_change"] = (
                diluted_change
            )

            if (
                diluted_change is None
                or abs(diluted_change - change) > 0.50
            ):
                diagnostic["status"] = (
                    "quarantined_series_discontinuity"
                )
                return None, diagnostic

            diagnostic["status"] = (
                "large_change_cross_checked"
            )

        return change, diagnostic

    def _diluted_yoy(self, series):
        if len(series.annual) < 2:
            return None

        latest = self.periods.resolve_latest_annual(
            series.annual
        ).fact
        if not latest:
            return None

        latest_end = date.fromisoformat(latest.end)
        candidates = []

        for prior in series.annual:
            if prior is latest or prior.value <= 0:
                continue

            gap = (
                latest_end
                - date.fromisoformat(prior.end)
            ).days

            if 300 <= gap <= 430:
                candidates.append(
                    (abs(gap - 365), prior)
                )

        if not candidates or latest.value <= 0:
            return None

        prior = min(candidates, key=lambda x: x[0])[1]
        return latest.value / prior.value - 1.0
