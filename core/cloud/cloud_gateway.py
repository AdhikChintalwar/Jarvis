from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.cloud.nvidia_client import (
    NvidiaNemotronClient,
)
from core.privacy import (
    CloudPrivacyGate,
)


@dataclass
class CloudReasoningResult:
    success: bool

    response: str | None = None
    blocked: bool = False

    reason: str | None = None

    redactions: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "response": self.response,
            "blocked": self.blocked,
            "reason": self.reason,
            "redactions": self.redactions or [],
        }


class CloudReasoningGateway:
    """
    Single cloud boundary for Baby.

    Agents must use this class instead of calling NVIDIA directly.
    """

    SYSTEM_PROMPT = """
You are BABY's remote reasoning engine.

You do NOT have direct access to the user's computer.

You cannot directly:
- read files
- inspect the desktop
- access passwords
- access API keys
- access browser cookies
- access Keychain
- execute commands

Local Baby agents perform actions.

You reason only over the sanitized context explicitly provided.

When more information is required, request it from a named local
agent rather than pretending you accessed it yourself.
""".strip()

    def __init__(
        self,
        *,
        client: NvidiaNemotronClient | None = None,
        privacy_gate: CloudPrivacyGate | None = None,
    ) -> None:
        self.client = (
            client
            or NvidiaNemotronClient()
        )

        self.privacy_gate = (
            privacy_gate
            or CloudPrivacyGate()
        )

    def reason(
        self,
        prompt: str,
        *,
        context: str | None = None,
        metadata: dict[str, Any] | None = None,
        reasoning: bool = True,
    ) -> CloudReasoningResult:

        combined = prompt

        if context:
            combined += (
                "\n\nLOCAL CONTEXT:\n"
                + context
            )

        prepared = (
            self.privacy_gate.prepare_text(
                combined,
                metadata=metadata,
            )
        )

        if not prepared.original_allowed:
            return CloudReasoningResult(
                success=False,
                blocked=True,
                reason=(
                    prepared.assessment.reason
                ),
                redactions=(
                    prepared.redactions
                ),
            )

        try:
            response = self.client.chat(
                messages=[
                    {
                        "role": "system",
                        "content": self.SYSTEM_PROMPT,
                    },
                    {
                        "role": "user",
                        "content": prepared.text,
                    },
                ],
                reasoning=reasoning,
            )

            return CloudReasoningResult(
                success=True,
                response=response,
                blocked=False,
                redactions=(
                    prepared.redactions
                ),
            )

        except Exception as error:
            return CloudReasoningResult(
                success=False,
                blocked=False,
                reason=str(error),
                redactions=(
                    prepared.redactions
                ),
            )