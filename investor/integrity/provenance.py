from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


SECTION_SOURCES = {
    "identity": "baby_investor.identity",
    "scanner": "baby_investor.scanner",
    "market": "yahoo_finance.market",
    "technical": "baby_investor.technical_engine",
    "fundamentals": "yahoo_finance.fundamentals",
    "financial_health": "baby_investor.financial_engine",
    "classification": "baby_investor.stock_classifier",
    "risk": "baby_investor.risk_engine",
    "sec": "sec_edgar.submissions",
    "deep_sec": "sec_edgar.filing_text",
    "catalysts": "baby_investor.catalyst_engine",
    "market_context": "baby_investor.market_context",
    "data_quality": "baby_investor.data_quality",
    "deterministic_thesis": "baby_investor.thesis_engine",
    "trade_plan": "baby_investor.trade_plan",
    "abnormal_volume": "baby_investor.abnormal_volume",
}


@dataclass
class ProvenanceRecord:
    section: str
    source: str
    present: bool
    field_count: int = 0
    notes: list[str] = field(
        default_factory=list
    )


class ProvenanceTracker:

    REQUIRED_SECTIONS = [
        "identity",
        "market",
        "technical",
        "risk",
    ]

    IMPORTANT_SECTIONS = [
        "fundamentals",
        "financial_health",
        "sec",
        "catalysts",
        "data_quality",
    ]

    def inspect(
        self,
        evidence: dict[str, Any],
    ) -> list[ProvenanceRecord]:

        records: list[ProvenanceRecord] = []

        for section, source in SECTION_SOURCES.items():
            payload = evidence.get(section)

            present = bool(payload)

            field_count = 0

            if isinstance(payload, dict):
                field_count = len(
                    [
                        key
                        for key, value
                        in payload.items()
                        if value not in (
                            None,
                            "",
                            [],
                            {},
                        )
                    ]
                )

            notes: list[str] = []

            if present and field_count == 0:
                notes.append(
                    "Section present but empty."
                )

            records.append(
                ProvenanceRecord(
                    section=section,
                    source=source,
                    present=present,
                    field_count=field_count,
                    notes=notes,
                )
            )

        return records

    def missing_sections(
        self,
        evidence: dict[str, Any],
    ) -> list[str]:

        missing: list[str] = []

        for section in self.REQUIRED_SECTIONS:
            if not evidence.get(section):
                missing.append(section)

        return missing

    def provenance_gaps(
        self,
        evidence: dict[str, Any],
    ) -> list[str]:

        gaps: list[str] = []

        for section in self.IMPORTANT_SECTIONS:
            payload = evidence.get(section)

            if not payload:
                gaps.append(
                    f"Missing optional section: {section}"
                )
                continue

            if isinstance(payload, dict):
                populated = any(
                    value not in (
                        None,
                        "",
                        [],
                        {},
                    )
                    for value in payload.values()
                )

                if not populated:
                    gaps.append(
                        f"Empty optional section: {section}"
                    )

        return gaps

    def source_for_path(
        self,
        path: str,
    ) -> str:

        section = path.split(
            ".",
            1,
        )[0]

        return SECTION_SOURCES.get(
            section,
            "unknown",
        )
