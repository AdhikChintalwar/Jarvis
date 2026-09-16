from __future__ import annotations

import threading
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class ToolPrivacy(str, Enum):
    PUBLIC = "public"

    # Executes locally and shouldn't normally expose data.
    LOCAL_ONLY = "local_only"

    # May return private information that should pass through
    # the privacy gateway before going to cloud.
    PRIVATE = "private"

    # Sensitive enough that cloud transfer is normally blocked.
    SENSITIVE = "sensitive"


@dataclass
class ToolParameter:
    type: str
    description: str = ""
    required: bool = True
    default: Any = None

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ToolDefinition:
    name: str
    agent: str
    description: str

    parameters: dict[
        str,
        ToolParameter,
    ] = field(
        default_factory=dict
    )

    privacy: ToolPrivacy = (
        ToolPrivacy.LOCAL_ONLY
    )

    confirmation_required: bool = False
    cloud_can_request: bool = True
    returns: str = ""

    # Existing executor compatibility
    mcp_tool: str | None = None
    arg_name: str | None = None
    spoken: str | None = None

    tags: list[str] = field(
        default_factory=list
    )

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return {
            "name": self.name,
            "agent": self.agent,
            "description": self.description,
            "parameters": {
                key: parameter.to_dict()
                for key, parameter
                in self.parameters.items()
            },
            "privacy": (
                self.privacy.value
            ),
            "confirmation_required": (
                self.confirmation_required
            ),
            "cloud_can_request": (
                self.cloud_can_request
            ),
            "returns": self.returns,

            "mcp_tool": (
                self.mcp_tool
                or self.name
            ),
            "arg_name": self.arg_name,
            "spoken": self.spoken,

            "tags": list(
                self.tags
            ),
        }


class ToolRegistry:
    """
    Source of truth describing what Baby knows how to do.

    This registry contains METADATA ONLY.

    Nemotron receives this metadata but never receives Python
    functions, filesystem access, MCP connections, credentials,
    or direct execution permissions.
    """

    def __init__(
        self,
    ) -> None:
        self._tools: dict[
            str,
            ToolDefinition,
        ] = {}

        self._lock = (
            threading.RLock()
        )

    def register(
        self,
        tool: ToolDefinition,
        *,
        replace: bool = False,
    ) -> ToolDefinition:
        normalized = (
            tool.name
            .strip()
            .lower()
        )

        if not normalized:
            raise ValueError(
                "Tool name cannot be empty."
            )

        with self._lock:
            if (
                normalized
                in self._tools
                and not replace
            ):
                raise ValueError(
                    f"Tool already registered: "
                    f"{normalized}"
                )

            tool.name = normalized

            self._tools[
                normalized
            ] = tool

        return tool

    def exists(
        self,
        name: str,
    ) -> bool:
        normalized = (
            name
            .strip()
            .lower()
        )

        with self._lock:
            return (
                normalized
                in self._tools
            )

    def get(
        self,
        name: str,
    ) -> ToolDefinition | None:
        normalized = (
            name
            .strip()
            .lower()
        )

        with self._lock:
            return self._tools.get(
                normalized
            )

    def list_tools(
        self,
        *,
        cloud_visible_only: bool = False,
    ) -> list[ToolDefinition]:

        with self._lock:
            tools = list(
                self._tools.values()
            )

        if cloud_visible_only:
            tools = [
                tool
                for tool in tools
                if tool.cloud_can_request
            ]

        return sorted(
            tools,
            key=lambda tool: (
                tool.name
            ),
        )

    def cloud_catalog(
        self,
    ) -> list[dict[str, Any]]:
        """
        Safe metadata catalog that can be given to Nemotron.
        """

        return [
            tool.to_dict()
            for tool
            in self.list_tools(
                cloud_visible_only=True
            )
        ]


tool_registry = ToolRegistry()


def register_builtin_tool_catalog(
) -> None:
    """
    Catalog of Baby tools currently known from the local system.

    This describes capabilities only; it does not implement them.
    """

    tools = [
        ToolDefinition(
            name="open_app",
            agent="desktop",
            description=(
                "Open a local macOS "
                "application by name."
            ),
            parameters={
                "app_name": ToolParameter(
                    type="string",
                    description=(
                        "macOS application name"
                    ),
                ),
            },
            privacy=(
                ToolPrivacy.LOCAL_ONLY
            ),
            returns=(
                "Whether the application "
                "was opened."
            ),
            tags=[
                "desktop",
                "application",
            ],
        ),

        ToolDefinition(
            name="open_website",
            agent="browser",
            description=(
                "Open a website in the "
                "local browser."
            ),
            parameters={
                "url": ToolParameter(
                    type="string",
                ),
            },
            privacy=(
                ToolPrivacy.LOCAL_ONLY
            ),
            returns=(
                "Browser execution status."
            ),
            tags=[
                "browser",
                "web",
            ],
        ),

        ToolDefinition(
            name="search_google",
            agent="browser",
            description=(
                "Search Google for a query "
                "using the local browser."
            ),
            parameters={
                "query": ToolParameter(
                    type="string",
                ),
            },
            privacy=(
                ToolPrivacy.LOCAL_ONLY
            ),
            returns=(
                "Search operation status."
            ),
            tags=[
                "browser",
                "search",
            ],
        ),

        ToolDefinition(
            name="search_youtube",
            agent="browser",
            description=(
                "Search YouTube for a query."
            ),
            parameters={
                "query": ToolParameter(
                    type="string",
                ),
            },
            privacy=(
                ToolPrivacy.LOCAL_ONLY
            ),
            tags=[
                "youtube",
                "browser",
            ],
        ),

        ToolDefinition(
            name="get_youtube_titles",
            agent="browser",
            description=(
                "Read YouTube result titles "
                "from the local browser."
            ),
            parameters={},
            privacy=(
                ToolPrivacy.PRIVATE
            ),
            returns=(
                "List of visible video titles."
            ),
            tags=[
                "youtube",
                "browser",
            ],
        ),

        ToolDefinition(
            name="play_first_youtube_video",
            agent="browser",
            description=(
                "Open the first visible "
                "YouTube search result."
            ),
            parameters={},
            privacy=(
                ToolPrivacy.LOCAL_ONLY
            ),
            tags=[
                "youtube",
            ],
        ),

        ToolDefinition(
            name="take_screenshot",
            agent="desktop",
            description=(
                "Capture the current Mac "
                "screen locally."
            ),
            parameters={},
            privacy=(
                ToolPrivacy.PRIVATE
            ),
            cloud_can_request=True,
            returns=(
                "Local screenshot reference."
            ),
            tags=[
                "screen",
                "desktop",
            ],
        ),

        ToolDefinition(
            name="analyze_screen",
            agent="desktop",
            description=(
                "Analyze what is currently "
                "visible on the Mac screen."
            ),
            parameters={
                "question": ToolParameter(
                    type="string",
                    required=False,
                    description=(
                        "Specific question about "
                        "the visible screen."
                    ),
                ),
            },
            privacy=(
                ToolPrivacy.PRIVATE
            ),
            returns=(
                "Screen analysis result."
            ),
            tags=[
                "screen",
                "vision",
            ],
        ),

        ToolDefinition(
            name="workspace_status",
            agent="workspace",
            description=(
                "Return the current project, "
                "path, Git branch and recent "
                "files."
            ),
            parameters={},
            privacy=(
                ToolPrivacy.PRIVATE
            ),
            returns=(
                "Sanitizable workspace metadata."
            ),
            tags=[
                "workspace",
                "git",
            ],
        ),

        ToolDefinition(
            name="workspace_recent_files",
            agent="workspace",
            description=(
                "Return recently modified "
                "project files."
            ),
            parameters={
                "limit": ToolParameter(
                    type="integer",
                    required=False,
                    default=10,
                ),
            },
            privacy=(
                ToolPrivacy.PRIVATE
            ),
            returns=(
                "List of project-relative files."
            ),
            tags=[
                "workspace",
                "files",
            ],
        ),

        ToolDefinition(
            name="current_time",
            agent="desktop",
            description=(
                "Return the current local time."
            ),
            parameters={},
            privacy=(
                ToolPrivacy.PUBLIC
            ),
            tags=[
                "time",
            ],
        ),
    ]

    for tool in tools:
        if not tool_registry.exists(
            tool.name
        ):
            tool_registry.register(
                tool
            )

def get_tool_descriptions() -> str:
    """
    Backward-compatible helper for older planner code.

    Returns a readable description of all registered tools.
    """
    lines: list[str] = []

    for tool in tool_registry.list_tools():
        parameter_parts = []

        for name, parameter in tool.parameters.items():
            required_text = (
                "required"
                if parameter.required
                else "optional"
            )

            parameter_parts.append(
                f"{name}: {parameter.type} ({required_text})"
            )

        parameters_text = (
            ", ".join(parameter_parts)
            if parameter_parts
            else "none"
        )

        lines.append(
            (
                f"- {tool.name}: {tool.description} "
                f"[agent={tool.agent}; "
                f"parameters={parameters_text}; "
                f"privacy={tool.privacy.value}]"
            )
        )

    return "\n".join(lines)


def get_tool_names() -> list[str]:
    """
    Return all registered tool names.
    """
    return [
        tool.name
        for tool in tool_registry.list_tools()
    ]

def get_registered_tool(
    name: str,
) -> dict[str, Any] | None:
    """
    Backward-compatible adapter for the existing executor.

    Returns the old dictionary shape expected by core/executor.py.
    """
    tool = tool_registry.get(name)

    if tool is None:
        return None

    return {
        "name": tool.name,
        "agent": tool.agent,
        "description": tool.description,

        # These fields preserve compatibility with the existing executor.
        "spoken": getattr(
            tool,
            "spoken",
            None,
        ),

        "mcp_tool": getattr(
            tool,
            "mcp_tool",
            tool.name,
        ),

        "arg_name": getattr(
            tool,
            "arg_name",
            None,
        ),

        "privacy": tool.privacy.value,
        "confirmation_required": (
            tool.confirmation_required
        ),
    }

def get_tool_catalog() -> list[dict[str, Any]]:
    """
    Return the complete tool metadata catalog.
    """
    return [
        tool.to_dict()
        for tool in tool_registry.list_tools()
    ]


register_builtin_tool_catalog()