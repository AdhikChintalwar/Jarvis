from __future__ import annotations

import json
import threading
from pathlib import Path

from core.mcp_proposals.models import (
    MCPToolProposal,
    ProposalStatus,
    utc_now_iso,
)


PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[2]
)

DATA_FILE = (
    PROJECT_ROOT
    / "data"
    / "mcp_proposals.json"
)

PORTAL_FILE = (
    PROJECT_ROOT
    / "baby-portal"
    / "public"
    / "mcp_proposals.json"
)


class MCPProposalStore:
    """
    Local persistent storage for Nemotron MCP proposals.
    """

    def __init__(
        self,
        *,
        data_file: Path = DATA_FILE,
        portal_file: Path = PORTAL_FILE,
    ) -> None:

        self.data_file = (
            data_file
        )

        self.portal_file = (
            portal_file
        )

        self._lock = (
            threading.RLock()
        )

        self.data_file.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.portal_file.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        if not self.data_file.exists():
            self._write(
                []
            )

    def list_all(
        self,
    ) -> list[MCPToolProposal]:

        with self._lock:
            data = self._read()

        return [
            MCPToolProposal.from_dict(
                item
            )
            for item in data
        ]

    def list_pending(
        self,
    ) -> list[MCPToolProposal]:

        return [
            proposal
            for proposal
            in self.list_all()
            if (
                proposal.status
                == ProposalStatus.PENDING
            )
        ]

    def get(
        self,
        proposal_id: str,
    ) -> MCPToolProposal | None:

        for proposal in self.list_all():
            if (
                proposal.id
                == proposal_id
            ):
                return proposal

        return None

    def save(
        self,
        proposal: MCPToolProposal,
    ) -> MCPToolProposal:

        with self._lock:
            proposals = (
                self.list_all()
            )

            replaced = False

            for index, existing in enumerate(
                proposals
            ):
                if (
                    existing.id
                    == proposal.id
                ):
                    proposals[
                        index
                    ] = proposal

                    replaced = True
                    break

            if not replaced:
                proposals.append(
                    proposal
                )

            self._write(
                [
                    item.to_dict()
                    for item
                    in proposals
                ]
            )

        return proposal

    def update_status(
        self,
        proposal_id: str,
        status: ProposalStatus,
    ) -> MCPToolProposal:

        proposal = self.get(
            proposal_id
        )

        if proposal is None:
            raise KeyError(
                f"MCP proposal not found: "
                f"{proposal_id}"
            )

        proposal.status = status
        proposal.updated_at = (
            utc_now_iso()
        )

        return self.save(
            proposal
        )

    def _read(
        self,
    ) -> list[dict]:

        if not self.data_file.exists():
            return []

        try:
            raw = (
                self.data_file
                .read_text(
                    encoding="utf-8"
                )
            )

            parsed = (
                json.loads(
                    raw
                )
            )

            if isinstance(
                parsed,
                list,
            ):
                return parsed

        except Exception:
            pass

        return []

    def _write(
        self,
        data: list[dict],
    ) -> None:

        serialized = (
            json.dumps(
                data,
                indent=2,
                ensure_ascii=False,
            )
        )

        self.data_file.write_text(
            serialized,
            encoding="utf-8",
        )

        self.portal_file.write_text(
            serialized,
            encoding="utf-8",
        )


proposal_store = (
    MCPProposalStore()
)