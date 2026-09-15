from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import date
from typing import Iterable


@dataclass
class NormalizedFact:
    metric: str
    value: float
    unit: str
    start: str | None
    end: str
    filed: str | None
    form: str | None
    accession: str | None
    fiscal_year: int | None
    fiscal_period: str | None
    frame: str | None
    taxonomy: str
    concept: str

    def to_dict(self) -> dict:
        return asdict(self)


class FinancialNormalizer:
    ANNUAL_FORMS = {"10-K", "20-F", "40-F"}
    QUARTER_FORMS = {"10-Q", "6-K"}

    def normalize_units(
        self,
        metric: str,
        taxonomy: str,
        concept: str,
        unit: str,
        rows: Iterable[dict],
    ) -> list[NormalizedFact]:
        output = []
        seen = set()

        for row in rows:
            if row.get("val") is None or not row.get("end"):
                continue

            try:
                value = float(row["val"])
            except (TypeError, ValueError):
                continue

            key = (
                row.get("start"),
                row.get("end"),
                value,
                row.get("form"),
                row.get("accn"),
                row.get("fp"),
                row.get("frame"),
            )
            if key in seen:
                continue
            seen.add(key)

            output.append(
                NormalizedFact(
                    metric=metric,
                    value=value,
                    unit=unit,
                    start=row.get("start"),
                    end=row["end"],
                    filed=row.get("filed"),
                    form=row.get("form"),
                    accession=row.get("accn"),
                    fiscal_year=row.get("fy"),
                    fiscal_period=row.get("fp"),
                    frame=row.get("frame"),
                    taxonomy=taxonomy,
                    concept=concept,
                )
            )

        output.sort(
            key=lambda x: (
                x.end,
                x.filed or "",
                x.accession or "",
            )
        )
        return output

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

    def annual(self, facts: list[NormalizedFact]) -> list[NormalizedFact]:
        candidates = []
        for fact in facts:
            duration = self.duration_days(fact)
            if fact.form not in self.ANNUAL_FORMS:
                continue
            if duration is not None and not (300 <= duration <= 430):
                continue
            candidates.append(fact)

        return self._canonical_duration_periods(candidates)

    def quarterly(self, facts: list[NormalizedFact]) -> list[NormalizedFact]:
        candidates = []
        for fact in facts:
            duration = self.duration_days(fact)
            if fact.form not in self.QUARTER_FORMS:
                continue
            if duration is not None and not (60 <= duration <= 120):
                continue
            candidates.append(fact)

        return self._canonical_duration_periods(candidates)

    def instantaneous(self, facts: list[NormalizedFact]) -> list[NormalizedFact]:
        candidates = [x for x in facts if not x.start]
        return self._canonical_instant_periods(candidates)

    @staticmethod
    def _canonical_duration_periods(
        facts: list[NormalizedFact],
    ) -> list[NormalizedFact]:
        """
        One observation per economic period.

        A later filing can repeat an older comparative period. We retain
        the most recently filed representation for the same start/end
        period, while keeping genuinely different periods separate.
        """
        by_period = {}

        for fact in facts:
            key = (fact.start, fact.end)
            old = by_period.get(key)

            if old is None:
                by_period[key] = fact
                continue

            old_key = (
                old.filed or "",
                old.accession or "",
            )
            new_key = (
                fact.filed or "",
                fact.accession or "",
            )

            if new_key >= old_key:
                by_period[key] = fact

        return sorted(
            by_period.values(),
            key=lambda x: (
                x.end,
                x.start or "",
            ),
        )

    @staticmethod
    def _canonical_instant_periods(
        facts: list[NormalizedFact],
    ) -> list[NormalizedFact]:
        """
        Instantaneous facts such as shares/cash/assets are keyed by
        balance-sheet date. Comparative values repeated in later filings
        are collapsed to one canonical value for that date.
        """
        by_date = {}

        for fact in facts:
            old = by_date.get(fact.end)

            if old is None:
                by_date[fact.end] = fact
                continue

            old_key = (
                old.filed or "",
                old.accession or "",
            )
            new_key = (
                fact.filed or "",
                fact.accession or "",
            )

            if new_key >= old_key:
                by_date[fact.end] = fact

        return sorted(
            by_date.values(),
            key=lambda x: x.end,
        )
