from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def utc_now_iso() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


@dataclass
class AgentMessage:
    sender: str
    recipient: str
    message_type: str
    content: str

    id: str = field(
        default_factory=lambda: (
            f"msg_{uuid4().hex[:12]}"
        )
    )

    created_at: str = field(
        default_factory=utc_now_iso
    )

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "sender": self.sender,
            "recipient": self.recipient,
            "message_type": self.message_type,
            "content": self.content,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }