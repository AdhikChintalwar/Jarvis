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
    freshness_days: int | None = None
    core_coverage: int = 0
    optional_coverage: int = 0
    diagnostics: dict | None = None

    def to_dict(self):
        return {
            "anchor_date": self.anchor_date,
            "metrics": {k: v.to_dict() for k, v in self.metrics.items()},
            "confidence": self.confidence,
            "status": self.status,
            "freshness_days": self.freshness_days,
            "core_coverage": self.core_coverage,
            "optional_coverage": self.optional_coverage,
            "diagnostics": self.diagnostics or {},
        }


class BalanceSheetResolver:
    """
    V3.3.1 recency-aware SEC balance-sheet resolver.

    Core rule:
      A stale complete snapshot must NOT beat a materially newer snapshot
      merely because the stale date contains an optional metric.

    Core metrics drive snapshot selection. Optional metrics can improve a
    snapshot but cannot drag the anchor backward.
    """

    MAX_MATCH_GAP_DAYS = 45
    MAX_ANCHOR_LAG_DAYS = 120

    CORE = (
        "cash",
        "assets",
        "liabilities",
        "equity",
        "debt_current",
        "debt_noncurrent",
    )

    OPTIONAL = (
        "short_term_investments",
    )

    def resolve(self, statements: dict[str, MetricSeries]) -> BalanceSheetSnapshot:
        names = self.CORE + self.OPTIONAL
        newest_core_date = self._newest_positive_date(statements, self.CORE)

        if newest_core_date is None:
            return BalanceSheetSnapshot(
                anchor_date=None,
                metrics={},
                confidence=0.0,
                status="missing",
                diagnostics={"reason": "No usable core balance-sheet facts."},
            )

        candidate_dates = self._candidate_dates(statements, self.CORE)

        # Prevent an old but complete snapshot from winning.
        fresh_candidates = [
            d for d in candidate_dates
            if self._days_between(newest_core_date, d) <= self.MAX_ANCHOR_LAG_DAYS
        ]
        if fresh_candidates:
            candidate_dates = fresh_candidates

        ranked = []

        for anchor in candidate_dates:
            resolved = {
                name: self._nearest(name, statements.get(name), anchor)
                for name in names
            }

            core_present = sum(
                1 for name in self.CORE
                if resolved[name].value is not None
            )
            optional_present = sum(
                1 for name in self.OPTIONAL
                if resolved[name].value is not None
            )

            core_quality = sum(
                resolved[name].confidence
                for name in self.CORE
                if resolved[name].value is not None
            )
            optional_quality = sum(
                resolved[name].confidence
                for name in self.OPTIONAL
                if resolved[name].value is not None
            )

            age_days = self._days_between(newest_core_date, anchor)
            recency = max(0.0, 1.0 - age_days / self.MAX_ANCHOR_LAG_DAYS)

            # Weighted score, rather than lexicographic "coverage first".
            # Recency and core coverage dominate optional coverage.
            score = (
                recency * 5.0
                + core_present * 2.0
                + core_quality * 0.75
                + optional_present * 0.20
                + optional_quality * 0.05
            )

            ranked.append({
                "anchor": anchor,
                "resolved": resolved,
                "core_present": core_present,
                "optional_present": optional_present,
                "core_quality": core_quality,
                "optional_quality": optional_quality,
                "age_days": age_days,
                "recency_score": recency,
                "score": score,
            })

        best = max(
            ranked,
            key=lambda x: (x["score"], x["anchor"]),
        )

        resolved = best["resolved"]
        present = [
            item.confidence for item in resolved.values()
            if item.value is not None
        ]
        base_conf = sum(present) / len(present) if present else 0.0

        freshness_multiplier = max(
            0.65,
            1.0 - best["age_days"] / 365.0,
        )
        confidence = min(0.99, base_conf * freshness_multiplier)

        core_present = best["core_present"]
        if core_present >= 5:
            status = "coherent_current"
        elif core_present >= 3:
            status = "partial_current"
        else:
            status = "weak_current"

        diagnostics = {
            "newest_core_date": newest_core_date,
            "selected_anchor": best["anchor"],
            "selected_score": best["score"],
            "selected_age_days": best["age_days"],
            "selection_rule": (
                "recency + core coverage + semantic/series quality; "
                "optional metrics cannot control anchor"
            ),
            "candidate_scores": [
                {
                    "anchor": x["anchor"],
                    "score": round(x["score"], 6),
                    "age_days": x["age_days"],
                    "core_coverage": x["core_present"],
                    "optional_coverage": x["optional_present"],
                    "recency_score": round(x["recency_score"], 6),
                }
                for x in sorted(ranked, key=lambda y: y["anchor"], reverse=True)[:12]
            ],
        }

        return BalanceSheetSnapshot(
            anchor_date=best["anchor"],
            metrics=resolved,
            confidence=confidence,
            status=status,
            freshness_days=best["age_days"],
            core_coverage=core_present,
            optional_coverage=best["optional_present"],
            diagnostics=diagnostics,
        )

    def _candidate_dates(self, statements, names):
        dates = set()
        for name in names:
            series = statements.get(name)
            if not series:
                continue
            for fact in series.instantaneous:
                if fact.value is not None:
                    dates.add(fact.end)
        return sorted(dates, reverse=True)

    def _newest_positive_date(self, statements, names):
        dates = []
        for name in names:
            series = statements.get(name)
            if not series:
                continue
            for fact in series.instantaneous:
                if fact.value is not None:
                    dates.append(fact.end)
        return max(dates) if dates else None

    def _nearest(self, metric, series, anchor):
        if not series or not series.instantaneous:
            return BalanceSheetMetric(
                metric, None, None, None, "missing", 0.0,
                "No instantaneous SEC fact."
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
            if gap <= self.MAX_MATCH_GAP_DAYS:
                candidates.append((gap, fact))

        if not candidates:
            return BalanceSheetMetric(
                metric, None, None, series.concept,
                "period_mismatch", 0.0,
                f"No fact within {self.MAX_MATCH_GAP_DAYS} days of {anchor}."
            )

        gap, fact = min(candidates, key=lambda x: (x[0], x[1].end),)

        confidence = max(
            0.50,
            min(
                0.98,
                series.series_quality * (1.0 - gap / 180.0),
            ),
        )

        return BalanceSheetMetric(
            metric=metric,
            value=fact.value,
            date=fact.end,
            concept=fact.concept,
            status="exact" if gap == 0 else "near_match",
            confidence=confidence,
            reason="Exact balance-sheet date." if gap == 0
            else f"Matched within {gap} days of anchor.",
        )

    @staticmethod
    def _days_between(a, b):
        return abs((date.fromisoformat(a) - date.fromisoformat(b)).days)
