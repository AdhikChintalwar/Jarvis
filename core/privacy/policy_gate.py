from __future__ import annotations

from pathlib import Path
from typing import Any

from core.privacy.classifier import PrivacyClassifier
from core.privacy.models import (
    CloudDecision,
    SanitizedPayload,
)
from core.privacy.sanitizer import PrivacySanitizer


class CloudPrivacyGate:
    """
    Mandatory gate between local Baby data and cloud models.
    """

    def __init__(self) -> None:
        self.classifier = PrivacyClassifier()
        self.sanitizer = PrivacySanitizer()

    def prepare_text(
        self,
        text: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> SanitizedPayload:
        assessment = self.classifier.assess_text(
            text
        )

        if assessment.decision == CloudDecision.BLOCK:
            return SanitizedPayload(
                original_allowed=False,
                text="",
                assessment=assessment,
                redactions=[],
                metadata=metadata or {},
            )

        if assessment.decision == CloudDecision.REDACT:
            sanitized, redactions = (
                self.sanitizer.sanitize_text(
                    text
                )
            )

            second_assessment = (
                self.classifier.assess_text(
                    sanitized
                )
            )

            if (
                second_assessment.decision
                == CloudDecision.BLOCK
            ):
                return SanitizedPayload(
                    original_allowed=False,
                    text="",
                    assessment=second_assessment,
                    redactions=redactions,
                    metadata=metadata or {},
                )

            return SanitizedPayload(
                original_allowed=True,
                text=sanitized,
                assessment=assessment,
                redactions=redactions,
                metadata=metadata or {},
            )

        sanitized, redactions = (
            self.sanitizer.sanitize_text(
                text
            )
        )

        return SanitizedPayload(
            original_allowed=True,
            text=sanitized,
            assessment=assessment,
            redactions=redactions,
            metadata=metadata or {},
        )

    def check_file(
        self,
        path: str | Path,
    ) -> bool:
        assessment = self.classifier.assess_path(
            path
        )

        return (
            assessment.decision
            != CloudDecision.BLOCK
        )