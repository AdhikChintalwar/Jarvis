from __future__ import annotations

import re
from pathlib import Path

from core.privacy.models import (
    CloudDecision,
    DataSensitivity,
    PrivacyAssessment,
    PrivacyFinding,
)


class PrivacyClassifier:
    """
    Local privacy classifier.

    It does not call any cloud service.
    """

    SECRET_PATTERNS = [
        (
            "private_key",
            re.compile(
                r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
                re.IGNORECASE,
            ),
        ),
        (
            "api_key",
            re.compile(
                r"\b(?:api[_-]?key|secret[_-]?key|access[_-]?token)"
                r"\s*[:=]\s*[\"']?[\w\-./+=]{12,}",
                re.IGNORECASE,
            ),
        ),
        (
            "bearer_token",
            re.compile(
                r"\bBearer\s+[A-Za-z0-9\-._~+/]+=*",
                re.IGNORECASE,
            ),
        ),
        (
            "github_token",
            re.compile(
                r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"
            ),
        ),
        (
            "aws_access_key",
            re.compile(
                r"\bAKIA[0-9A-Z]{16}\b"
            ),
        ),
    ]

    SENSITIVE_PATTERNS = [
        (
            "email_address",
            re.compile(
                r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
                re.IGNORECASE,
            ),
        ),
        (
            "phone_number",
            re.compile(
                r"(?<!\d)(?:\+?1[-.\s]?)?"
                r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}(?!\d)"
            ),
        ),
        (
            "ssn",
            re.compile(
                r"\b\d{3}-\d{2}-\d{4}\b"
            ),
        ),
        (
            "credit_card_like",
            re.compile(
                r"\b(?:\d[ -]*?){13,19}\b"
            ),
        ),
    ]

    BLOCKED_PATH_PARTS = {
        ".ssh",
        ".aws",
        ".gnupg",
        "keychains",
        "cookies",
        "login data",
    }

    BLOCKED_FILENAMES = {
        ".env",
        ".env.local",
        ".env.production",
        "id_rsa",
        "id_ed25519",
        "credentials",
        "credentials.json",
        "secrets.json",
    }

    def assess_text(
        self,
        text: str,
    ) -> PrivacyAssessment:
        if not isinstance(text, str):
            raise TypeError(
                "Privacy classifier expects text."
            )

        findings: list[PrivacyFinding] = []

        for category, pattern in self.SECRET_PATTERNS:
            match = pattern.search(text)

            if match:
                findings.append(
                    PrivacyFinding(
                        category=category,
                        sensitivity=DataSensitivity.SECRET,
                        reason=(
                            "Credential or authentication material "
                            "must never be sent to cloud models."
                        ),
                        value_preview=self._preview(
                            match.group(0)
                        ),
                    )
                )

        if findings:
            return PrivacyAssessment(
                sensitivity=DataSensitivity.SECRET,
                decision=CloudDecision.BLOCK,
                findings=findings,
                reason=(
                    "Payload contains credential-like or secret data."
                ),
            )

        for category, pattern in self.SENSITIVE_PATTERNS:
            match = pattern.search(text)

            if match:
                findings.append(
                    PrivacyFinding(
                        category=category,
                        sensitivity=DataSensitivity.SENSITIVE,
                        reason=(
                            "Personal or sensitive value should be "
                            "redacted before cloud transmission."
                        ),
                        value_preview=self._preview(
                            match.group(0)
                        ),
                    )
                )

        if findings:
            return PrivacyAssessment(
                sensitivity=DataSensitivity.SENSITIVE,
                decision=CloudDecision.REDACT,
                findings=findings,
                reason=(
                    "Payload can be sent only after local redaction."
                ),
            )

        return PrivacyAssessment(
            sensitivity=DataSensitivity.INTERNAL,
            decision=CloudDecision.ALLOW,
            findings=[],
            reason="No blocked or sensitive patterns detected.",
        )

    def assess_path(
        self,
        path: str | Path,
    ) -> PrivacyAssessment:
        path_obj = Path(path).expanduser()

        normalized_parts = {
            part.lower()
            for part in path_obj.parts
        }

        filename = path_obj.name.lower()

        if (
            filename in self.BLOCKED_FILENAMES
            or normalized_parts.intersection(
                self.BLOCKED_PATH_PARTS
            )
        ):
            return PrivacyAssessment(
                sensitivity=DataSensitivity.SECRET,
                decision=CloudDecision.BLOCK,
                findings=[
                    PrivacyFinding(
                        category="restricted_path",
                        sensitivity=DataSensitivity.SECRET,
                        reason=(
                            f"Restricted local path: {path_obj}"
                        ),
                    )
                ],
                reason=(
                    "Files from credential or secret locations "
                    "cannot be sent to cloud models."
                ),
            )

        return PrivacyAssessment(
            sensitivity=DataSensitivity.PRIVATE,
            decision=CloudDecision.REDACT,
            findings=[],
            reason=(
                "Local file content requires inspection before "
                "cloud transmission."
            ),
        )

    @staticmethod
    def _preview(
        value: str,
    ) -> str:
        if len(value) <= 8:
            return "***"

        return (
            value[:3]
            + "***"
            + value[-3:]
        )