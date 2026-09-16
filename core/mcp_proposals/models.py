from __future__ import annotations

from dataclasses import (
    asdict,
    dataclass,
    field,
)
from datetime import (
    datetime,
    timezone,
)
from enum import Enum
from typing import Any
from uuid import uuid4


def utc_now_iso() -> str:
    return (
        datetime.now(
            timezone.utc
        )
        .isoformat()
    )


class ProposalStatus(
    str,
    Enum,
):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    IMPLEMENTED = "implemented"


@dataclass
class MCPToolProposal:
    name: str
    reason: str
    description: str

    suggested_agent: str

    inputs: dict[
        str,
        Any,
    ] = field(
        default_factory=dict
    )

    expected_output: dict[
        str,
        Any,
    ] = field(
        default_factory=dict
    )

    privacy: str = "private"

    confirmation_required: bool = True

    user_request: str = ""

    id: str = field(
        default_factory=lambda: (
            "mcp_"
            + uuid4().hex[:12]
        )
    )

    status: ProposalStatus = (
        ProposalStatus.PENDING
    )

    created_at: str = field(
        default_factory=utc_now_iso
    )

    updated_at: str = field(
        default_factory=utc_now_iso
    )

    metadata: dict[
        str,
        Any,
    ] = field(
        default_factory=dict
    )

    def to_dict(
        self,
    ) -> dict[str, Any]:
        data = asdict(self)

        data["status"] = (
            self.status.value
        )

        return data

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
    ) -> "MCPToolProposal":

        return cls(
            id=data["id"],
            name=data["name"],
            reason=data.get(
                "reason",
                "",
            ),
            description=data.get(
                "description",
                "",
            ),
            suggested_agent=data.get(
                "suggested_agent",
                "planner",
            ),
            inputs=data.get(
                "inputs",
                {},
            ),
            expected_output=data.get(
                "expected_output",
                {},
            ),
            privacy=data.get(
                "privacy",
                "private",
            ),
            confirmation_required=(
                data.get(
                    "confirmation_required",
                    True,
                )
            ),
            user_request=data.get(
                "user_request",
                "",
            ),
            status=ProposalStatus(
                data.get(
                    "status",
                    "pending",
                )
            ),
            created_at=data.get(
                "created_at",
                utc_now_iso(),
            ),
            updated_at=data.get(
                "updated_at",
                utc_now_iso(),
            ),
            metadata=data.get(
                "metadata",
                {},
            ),
        )