from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class DataSensitivity(str, Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    PRIVATE = "private"
    SENSITIVE = "sensitive"
    SECRET = "secret"


class CloudDecision(str, Enum):
    ALLOW = "allow"
    REDACT = "redact"
    BLOCK = "block"


@dataclass
class PrivacyFinding:
    category: str
    sensitivity: DataSensitivity
    reason: str
    value_preview: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "sensitivity": self.sensitivity.value,
            "reason": self.reason,
            "value_preview": self.value_preview,
        }


@dataclass
class PrivacyAssessment:
    sensitivity: DataSensitivity
    decision: CloudDecision

    findings: list[PrivacyFinding] = field(
        default_factory=list
    )

    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "sensitivity": self.sensitivity.value,
            "decision": self.decision.value,
            "reason": self.reason,
            "findings": [
                finding.to_dict()
                for finding in self.findings
            ],
        }


@dataclass
class SanitizedPayload:
    original_allowed: bool
    text: str

    assessment: PrivacyAssessment

    redactions: list[str] = field(
        default_factory=list
    )

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "original_allowed": self.original_allowed,
            "text": self.text,
            "assessment": self.assessment.to_dict(),
            "redactions": self.redactions,
            "metadata": self.metadata,
        }