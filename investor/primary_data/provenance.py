from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any


@dataclass
class Provenance:
    source: str
    source_url: str | None = None
    retrieved_at: str | None = None
    filing_form: str | None = None
    filing_date: str | None = None
    period_start: str | None = None
    period_end: str | None = None
    accession_number: str | None = None
    taxonomy: str | None = None
    concept: str | None = None
    unit: str | None = None
    calculated_by: str | None = None
    confidence: float = 1.0

    def __post_init__(self):
        if not self.retrieved_at:
            self.retrieved_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PrimaryMetric:
    name: str
    value: Any
    provenance: Provenance

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "value": self.value,
            "provenance": self.provenance.to_dict(),
        }
