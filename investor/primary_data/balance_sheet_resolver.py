from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import date

from .financial_statements import MetricSeries


@dataclass
class BalanceSheetMetric:
    metric: str
    value: float | None
    date: str | None
    concept: str | None
    status: str
    confidence: float
    reason: str

    def to_dict(self):
        return asdict(self)


@dataclass
class BalanceSheetSnapshot:
    anchor_date: str | None
    metrics: dict[str, BalanceSheetMetric]
    confidence: float
    status: str

    def to_dict(self):
        return {
            "anchor_date": self.anchor_date,
            "metrics": {
                k: v.to_dict()
                for k, v in self.metrics.items()
            },
            "confidence": self.confidence,
            "status": self.status,
        }


class BalanceSheetResolver:
    """
    Builds one coherent balance-sheet snapshot.

    Never adds cash from one date to investments/debt from a distant date.
    """

    MAX_GAP_DAYS = 45

    def resolve(
        self,
        statements: dict[str, MetricSeries],
    ) -> BalanceSheetSnapshot:
        names = [
            "cash",
            "short_term_investments",
            "assets",
            "liabilities",
            "equity",
            "debt_current",
            "debt_noncurrent",
        ]

        all_dates = []
        for name in names:
            series = statements.get(name)
            if not series:
                continue
            for fact in series.instantaneous:
                if fact.value is not None:
                    all_dates.append(fact.end)

        if not all_dates:
            return BalanceSheetSnapshot(
                None, {}, 0.0, "missing"
            )

        # Prefer the newest date that has broad metric coverage.
        candidate_dates = sorted(set(all_dates), reverse=True)
        scored = []

        for anchor in candidate_dates:
            resolved = {}
            coverage = 0
            quality_sum = 0.0

            for name in names:
                item = self._nearest(
                    name,
                    statements.get(name),
                    anchor,
                )
                resolved[name] = item

                if item.value is not None:
                    coverage += 1
                    quality_sum += item.confidence

            scored.append(
                (
                    coverage,
                    quality_sum,
                    anchor,
                    resolved,
                )
            )

        coverage, quality_sum, anchor, metrics = max(
            scored,
            key=lambda x: (
                x[0],
                x[1],
                x[2],
            ),
        )

        confidence = (
            quality_sum / coverage
            if coverage else 0.0
        )

        if coverage >= 5:
            status = "coherent"
        elif coverage >= 3:
            status = "partial"
        else:
            status = "weak"

        return BalanceSheetSnapshot(
            anchor_date=anchor,
            metrics=metrics,
            confidence=confidence,
            status=status,
        )

    def _nearest(
        self,
        metric: str,
        series: MetricSeries | None,
        anchor: str,
    ) -> BalanceSheetMetric:
        if not series or not series.instantaneous:
            return BalanceSheetMetric(
                metric, None, None, None,
                "missing", 0.0,
                "No instantaneous SEC fact.",
            )

        anchor_date = date.fromisoformat(anchor)
        candidates = []

        for fact in series.instantaneous:
            if fact.value is None:
                continue

            try:
                fact_date = date.fromisoformat(fact.end)
            except ValueError:
                continue

            gap = abs((anchor_date - fact_date).days)

            if gap <= self.MAX_GAP_DAYS:
                candidates.append((gap, fact))

        if not candidates:
            return BalanceSheetMetric(
                metric, None, None, series.concept,
                "period_mismatch", 0.0,
                f"No fact within {self.MAX_GAP_DAYS} days of {anchor}.",
            )

        gap, fact = min(
            candidates,
            key=lambda x: (
                x[0],
                -(date.fromisoformat(x[1].end).toordinal()),
            ),
        )

        confidence = max(
            0.55,
            min(
                0.98,
                series.series_quality
                * (1.0 - gap / 180.0),
            ),
        )

        return BalanceSheetMetric(
            metric=metric,
            value=fact.value,
            date=fact.end,
            concept=fact.concept,
            status="exact" if gap == 0 else "near_match",
            confidence=confidence,
            reason=(
                "Exact balance-sheet date."
                if gap == 0
                else f"Matched within {gap} days of anchor."
            ),
        )
