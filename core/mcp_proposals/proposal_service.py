from __future__ import annotations

from typing import Any

from core.event_bus import publish

from core.mcp_proposals.models import (
    MCPToolProposal,
)
from core.mcp_proposals.proposal_store import (
    MCPProposalStore,
    proposal_store,
)


class MCPProposalService:
    """
    Handles Nemotron's requests for new Baby capabilities.

    IMPORTANT:
    Creating a proposal does NOT create, install, register,
    or execute a tool.
    """

    def __init__(
        self,
        store: MCPProposalStore | None = None,
    ) -> None:

        self.store = (
            store
            or proposal_store
        )

    def create_from_nemotron(
        self,
        *,
        user_request: str,
        proposal_data: dict[
            str,
            Any,
        ],
    ) -> MCPToolProposal:

        name = str(
            proposal_data.get(
                "name",
                "",
            )
        ).strip()

        if not name:
            raise ValueError(
                "Nemotron MCP proposal "
                "is missing a tool name."
            )

        proposal = MCPToolProposal(
            name=name,
            reason=str(
                proposal_data.get(
                    "reason",
                    "",
                )
            ),
            description=str(
                proposal_data.get(
                    "description",
                    "",
                )
            ),
            suggested_agent=str(
                proposal_data.get(
                    "suggested_agent",
                    "planner",
                )
            ),
            inputs=proposal_data.get(
                "inputs",
                {},
            ),
            expected_output=(
                proposal_data.get(
                    "expected_output",
                    {},
                )
            ),
            privacy=str(
                proposal_data.get(
                    "privacy",
                    "private",
                )
            ),
            confirmation_required=bool(
                proposal_data.get(
                    "confirmation_required",
                    True,
                )
            ),
            user_request=(
                user_request
            ),
            metadata={
                "requested_by": (
                    "nemotron"
                ),
            },
        )

        self.store.save(
            proposal
        )

        publish(
            "mcp_tool_proposed",
            {
                "proposal_id": (
                    proposal.id
                ),
                "name": (
                    proposal.name
                ),
                "reason": (
                    proposal.reason
                ),
            },
        )

        print(
            "Nemotron proposed MCP tool:",
            proposal.name,
        )

        return proposal


proposal_service = (
    MCPProposalService()
)