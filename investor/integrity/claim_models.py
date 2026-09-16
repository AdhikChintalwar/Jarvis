from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class ClaimType(str, Enum):
    FACT = "FACT"
    CALCULATION = "CALCULATION"
    INFERENCE = "INFERENCE"
    UNKNOWN = "UNKNOWN"


class ClaimCategory(str, Enum):
    STRENGTH = "STRENGTH"
    RISK = "RISK"
    RATIONALE = "RATIONALE"
    ACTION = "ACTION"
    CATALYST = "CATALYST"
    OTHER = "OTHER"


@dataclass
class EvidenceItem:
    evidence_id: str
    value: Any

    source: str
    retrieved_at: str | None = None

    reliability: str = "medium"
    description: str | None = None

    def to_dict(self):
        return asdict(self)


@dataclass
class ClaimRecord:
    claim_id: str

    statement: str

    claim_type: ClaimType

    category: ClaimCategory = ClaimCategory.OTHER

    evidence_ids: list[str] = field(
        default_factory=list
    )

    confidence: float = 0.0

    supported: bool = False

    validation_reason: str | None = None

    def to_dict(self):
        data = asdict(self)

        data["claim_type"] = (
            self.claim_type.value
        )

        data["category"] = (
            self.category.value
        )

        return data


@dataclass
class IntegrityResult:
    passed: bool

    supported_claims: list[ClaimRecord] = field(
        default_factory=list
    )

    unsupported_claims: list[ClaimRecord] = field(
        default_factory=list
    )

    unknown_claims: list[ClaimRecord] = field(
        default_factory=list
    )

    evidence_used: list[str] = field(
        default_factory=list
    )

    integrity_score: float = 100.0

    warnings: list[str] = field(
        default_factory=list
    )

    def to_dict(self):
        return {
            "passed": self.passed,

            "supported_claims": [
                item.to_dict()
                for item
                in self.supported_claims
            ],

            "unsupported_claims": [
                item.to_dict()
                for item
                in self.unsupported_claims
            ],

            "unknown_claims": [
                item.to_dict()
                for item
                in self.unknown_claims
            ],

            "evidence_used":
                self.evidence_used,

            "integrity_score":
                self.integrity_score,

            "warnings":
                self.warnings,
        }