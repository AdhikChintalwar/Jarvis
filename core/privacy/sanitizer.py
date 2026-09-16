from __future__ import annotations

import re

from core.privacy.classifier import PrivacyClassifier


class PrivacySanitizer:
    """
    Removes sensitive values locally before cloud transmission.
    """

    REPLACEMENTS = {
        "email_address": "[REDACTED_EMAIL]",
        "phone_number": "[REDACTED_PHONE]",
        "ssn": "[REDACTED_SSN]",
        "credit_card_like": "[REDACTED_PAYMENT_NUMBER]",
    }

    PATH_PATTERN = re.compile(
        r"/Users/[^/\s]+"
    )

    HOME_PATTERN = re.compile(
        r"(?:~|/Users/[^/\s]+)/"
    )

    def __init__(self) -> None:
        self.classifier = PrivacyClassifier()

    def sanitize_text(
        self,
        text: str,
    ) -> tuple[str, list[str]]:
        if not isinstance(text, str):
            raise TypeError(
                "Sanitizer expects text."
            )

        sanitized = text
        redactions: list[str] = []

        for (
            category,
            pattern,
        ) in self.classifier.SENSITIVE_PATTERNS:

            replacement = self.REPLACEMENTS.get(
                category,
                "[REDACTED]",
            )

            if pattern.search(sanitized):
                sanitized = pattern.sub(
                    replacement,
                    sanitized,
                )
                redactions.append(category)

        sanitized, path_count = (
            self.PATH_PATTERN.subn(
                "/Users/[LOCAL_USER]",
                sanitized,
            )
        )

        if path_count:
            redactions.append(
                "local_username_path"
            )

        return sanitized, redactions