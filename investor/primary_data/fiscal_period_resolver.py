from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable

from .financial_normalizer import NormalizedFact


@dataclass
class ResolvedPeriod:
    fact: NormalizedFact | None
    status: str
    confidence: float
    reason: str

    def to_dict(self) -> dict:
        return {
            "fact": self.fact.to_dict() if self.fact else None,
            "status": self.status,
            "confidence": self.confidence,
            "reason": self.reason,
        }


class FiscalPeriodResolver:
    ANNUAL_FORMS = {"10-K", "20-F", "40-F"}

    @staticmethod
    def duration_days(fact: NormalizedFact) -> int | None:
        if not fact.start:
            return None
        try:
            return (
                date.fromisoformat(fact.end)
                - date.fromisoformat(fact.start)
            ).days
        except ValueError:
            return None

    def annual_candidates(
        self,
        rows: Iterable[NormalizedFact],
    ) -> list[NormalizedFact]:
        out = []

        for fact in rows:
            if fact.form not in self.ANNUAL_FORMS:
                continue

            duration = self.duration_days(fact)
            if duration is not None and not (300 <= duration <= 430):
                continue

            out.append(fact)

        return sorted(
            out,
            key=lambda x: (
                x.end,
                x.filed or "",
                x.accession or "",
            ),
        )

    def resolve_latest_annual(
        self,
        rows: Iterable[NormalizedFact],
    ) -> ResolvedPeriod:
        candidates = self.annual_candidates(rows)

        if not candidates:
            return ResolvedPeriod(
                None, "missing", 0.0,
                "No comparable annual duration fact found.",
            )

        latest_end = max(x.end for x in candidates)
        latest = [x for x in candidates if x.end == latest_end]

        fact = max(
            latest,
            key=lambda x: (
                x.fiscal_period == "FY",
                x.filed or "",
                x.accession or "",
            ),
        )

        confidence = 0.95 if fact.fiscal_period == "FY" else 0.88

        return ResolvedPeriod(
            fact,
            "resolved",
            confidence,
            "Latest annual economic period selected.",
        )

    def resolve_same_period(
        self,
        numerator: Iterable[NormalizedFact],
        denominator: Iterable[NormalizedFact],
        *,
        anchor_end: str | None = None,
        max_anchor_gap_days: int = 45,
    ) -> tuple[ResolvedPeriod, ResolvedPeriod]:
        """
        Resolve the newest comparable pair, optionally anchored to the
        company's latest selected annual revenue period.

        This prevents an old exact pair (e.g. 2017) from representing a
        current company merely because newer facts do not align exactly.
        """
        nums = self.annual_candidates(numerator)
        dens = self.annual_candidates(denominator)

        if not nums or not dens:
            missing = ResolvedPeriod(
                None, "unresolved", 0.0,
                "Numerator or denominator has no annual candidates.",
            )
            return missing, missing

        exact = []

        for num in nums:
            for den in dens:
                if num.start == den.start and num.end == den.end:
                    exact.append((num, den))

        if exact:
            exact.sort(
                key=lambda pair: (
                    pair[0].end,
                    pair[0].filed or "",
                    pair[1].filed or "",
                ),
                reverse=True,
            )

            for num, den in exact:
                if self._within_anchor(
                    num.end,
                    anchor_end,
                    max_anchor_gap_days,
                ):
                    return (
                        ResolvedPeriod(
                            num, "exact", 0.99,
                            "Newest exact pair aligned with latest annual anchor.",
                        ),
                        ResolvedPeriod(
                            den, "exact", 0.99,
                            "Newest exact pair aligned with latest annual anchor.",
                        ),
                    )

        near = []

        for num in nums:
            if not num.start:
                continue

            try:
                ns = date.fromisoformat(num.start)
                ne = date.fromisoformat(num.end)
            except ValueError:
                continue

            for den in dens:
                if not den.start:
                    continue

                try:
                    ds = date.fromisoformat(den.start)
                    de = date.fromisoformat(den.end)
                except ValueError:
                    continue

                start_gap = abs((ns - ds).days)
                end_gap = abs((ne - de).days)

                if start_gap <= 7 and end_gap <= 7:
                    near.append(
                        (
                            max(num.end, den.end),
                            start_gap + end_gap,
                            num,
                            den,
                        )
                    )

        near.sort(
            key=lambda x: (
                x[0],
                -x[1],
            ),
            reverse=True,
        )

        for _, _, num, den in near:
            pair_end = max(num.end, den.end)

            if self._within_anchor(
                pair_end,
                anchor_end,
                max_anchor_gap_days,
            ):
                return (
                    ResolvedPeriod(
                        num, "near_match", 0.88,
                        "Newest near-matched pair aligned with latest annual anchor.",
                    ),
                    ResolvedPeriod(
                        den, "near_match", 0.88,
                        "Newest near-matched pair aligned with latest annual anchor.",
                    ),
                )

        reason = (
            "No comparable pair near the latest annual anchor."
            if anchor_end
            else "No comparable annual pair found."
        )

        missing = ResolvedPeriod(
            None, "unresolved", 0.0, reason
        )
        return missing, missing

    @staticmethod
    def _within_anchor(
        fact_end: str,
        anchor_end: str | None,
        max_gap: int,
    ) -> bool:
        if not anchor_end:
            return True

        try:
            a = date.fromisoformat(anchor_end)
            f = date.fromisoformat(fact_end)
        except ValueError:
            return False

        return abs((a - f).days) <= max_gap
