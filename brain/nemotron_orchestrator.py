from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from core.cloud import (
    CloudReasoningGateway,
)
from core.mcp_proposals import (
    MCPToolProposal,
    proposal_service,
)
from core.tool_registry import (
    register_builtin_tool_catalog,
    tool_registry,
)


@dataclass
class OrchestratorResult:
    success: bool

    decision: str

    answer: str = ""

    plan: list[
        dict[str, Any]
    ] | None = None

    proposal: (
        MCPToolProposal
        | None
    ) = None

    blocked: bool = False

    raw_response: (
        str | None
    ) = None

    error: (
        str | None
    ) = None

    def to_dict(
        self,
    ) -> dict[str, Any]:

        return {
            "success": (
                self.success
            ),
            "decision": (
                self.decision
            ),
            "answer": (
                self.answer
            ),
            "plan": (
                self.plan
            ),
            "proposal": (
                self.proposal.to_dict()
                if self.proposal
                else None
            ),
            "blocked": (
                self.blocked
            ),
            "error": (
                self.error
            ),
        }


class NemotronOrchestrator:
    """
    Cloud reasoning coordinator for complex Baby requests.

    Nemotron receives:
        - sanitized user request
        - safe tool metadata
        - safe agent descriptions

    Nemotron NEVER receives:
        - executable tool handles
        - filesystem access
        - shell access
        - passwords
        - API keys
        - browser cookies
        - Keychain access
    """

    AGENTS = {
        "desktop": (
            "Controls approved local "
            "macOS operations."
        ),
        "browser": (
            "Performs local browser "
            "navigation and searches."
        ),
        "coding": (
            "Analyzes and works with code."
        ),
        "workspace": (
            "Inspects local project and "
            "Git information."
        ),
        "memory": (
            "Retrieves approved Baby "
            "memory."
        ),
        "planner": (
            "Coordinates complex local "
            "workflows."
        ),
    }

    def __init__(
        self,
        *,
        gateway: (
            CloudReasoningGateway
            | None
        ) = None,
    ) -> None:

        register_builtin_tool_catalog()

        self.gateway = (
            gateway
            or CloudReasoningGateway()
        )

    def plan(
        self,
        user_request: str,
        *,
        local_context: (
            str | None
        ) = None,
    ) -> OrchestratorResult:

        prompt = (
            self._build_prompt(
                user_request
            )
        )

        result = (
            self.gateway.reason(
                prompt,
                context=local_context,
                metadata={
                    "purpose": (
                        "baby_orchestration"
                    ),
                },
            )
        )

        if not result.success:
            return OrchestratorResult(
                success=False,
                decision="error",
                blocked=result.blocked,
                error=(
                    result.reason
                ),
            )

        raw = (
            result.response
            or ""
        )

        parsed = (
            self._parse_json(
                raw
            )
        )

        if parsed is None:
            return OrchestratorResult(
                success=True,
                decision="answer",
                answer=raw,
                raw_response=raw,
            )

        decision = str(
            parsed.get(
                "decision",
                "answer",
            )
        ).lower()

        # =====================================================
        # Nemotron identified a missing capability.
        # =====================================================

        if (
            decision
            == "propose_tool"
        ):

            proposal_data = (
                parsed.get(
                    "proposal"
                )
            )

            if not isinstance(
                proposal_data,
                dict,
            ):
                return OrchestratorResult(
                    success=False,
                    decision="error",
                    error=(
                        "Nemotron requested a "
                        "tool proposal without "
                        "proposal data."
                    ),
                    raw_response=raw,
                )

            proposal = (
                proposal_service
                .create_from_nemotron(
                    user_request=(
                        user_request
                    ),
                    proposal_data=(
                        proposal_data
                    ),
                )
            )

            return OrchestratorResult(
                success=True,
                decision=(
                    "propose_tool"
                ),
                answer=str(
                    parsed.get(
                        "answer",
                        (
                            "A new capability "
                            "would be useful."
                        ),
                    )
                ),
                proposal=proposal,
                raw_response=raw,
            )

        # =====================================================
        # Existing tools are enough.
        # =====================================================

        plan = parsed.get(
            "plan"
        )

        if not isinstance(
            plan,
            list,
        ):
            plan = []

        return OrchestratorResult(
            success=True,
            decision=decision,
            answer=str(
                parsed.get(
                    "answer",
                    "",
                )
            ),
            plan=plan,
            raw_response=raw,
        )

    def _build_prompt(
        self,
        user_request: str,
    ) -> str:

        agents = json.dumps(
            self.AGENTS,
            indent=2,
        )

        tools = json.dumps(
            tool_registry.cloud_catalog(),
            indent=2,
        )

        return f"""
You are the orchestration brain for BABY, a local Mac assistant.

USER REQUEST:
{user_request}

AVAILABLE LOCAL AGENTS:
{agents}

AVAILABLE TOOLS:
{tools}

IMPORTANT SECURITY RULES:

1. You have NO direct access to the computer.
2. You cannot execute tools yourself.
3. Local Baby agents execute approved tools.
4. Never ask for:
   - passwords
   - API keys
   - authentication tokens
   - browser cookies
   - SSH private keys
   - .env contents
   - Keychain contents
5. Use the minimum amount of private information necessary.
6. Private tool results must be sanitized before cloud transmission.
7. You may suggest a NEW MCP tool if existing tools cannot reasonably
   accomplish the user's request.
8. A proposed MCP tool is only a suggestion. You cannot install,
   activate, generate, or execute it yourself.
9. Do not propose a new tool when the task can reasonably be completed
   by combining existing tools.

RETURN STRICT JSON ONLY.

If existing tools are sufficient:

{{
  "decision": "plan",
  "answer": "short explanation",
  "plan": [
    {{
      "agent": "workspace",
      "tool": "workspace_status",
      "arguments": {{}},
      "purpose": "why this step is necessary"
    }}
  ]
}}

If an important capability is missing:

{{
  "decision": "propose_tool",
  "answer": "short explanation",
  "proposal": {{
    "name": "snake_case_tool_name",
    "reason": "why existing tools are insufficient",
    "description": "what this proposed MCP tool should do",
    "suggested_agent": "agent name",
    "inputs": {{
      "example_argument": {{
        "type": "string",
        "description": "what it means"
      }}
    }},
    "expected_output": {{
      "result": "description"
    }},
    "privacy": "public|local_only|private|sensitive",
    "confirmation_required": true
  }}
}}

Do not include Markdown.
Do not include commentary outside the JSON.
""".strip()

    @staticmethod
    def _parse_json(
        text: str,
    ) -> dict[
        str,
        Any,
    ] | None:

        cleaned = (
            text.strip()
        )

        # Remove accidental markdown fences.
        cleaned = re.sub(
            r"^```(?:json)?\s*",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )

        cleaned = re.sub(
            r"\s*```$",
            "",
            cleaned,
        )

        try:
            parsed = json.loads(
                cleaned
            )

            if isinstance(
                parsed,
                dict,
            ):
                return parsed

        except json.JSONDecodeError:
            pass

        # Try extracting first JSON object.
        start = cleaned.find(
            "{"
        )

        end = cleaned.rfind(
            "}"
        )

        if (
            start >= 0
            and end > start
        ):
            try:
                parsed = (
                    json.loads(
                        cleaned[
                            start:
                            end + 1
                        ]
                    )
                )

                if isinstance(
                    parsed,
                    dict,
                ):
                    return parsed

            except json.JSONDecodeError:
                pass

        return None