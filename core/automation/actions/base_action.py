from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from core.automation.models import Automation


@dataclass
class ActionContext:
    """
    Information available to an action during execution.

    `state` is shared across the entire action pipeline.
    Each action can read results produced by earlier actions.
    """

    automation: Automation
    action_index: int

    state: dict[str, Any] = field(default_factory=dict)
    previous_result: Any = None

    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ActionResult:
    """
    Standard result returned by every action plugin.
    """

    success: bool
    data: Any = None
    message: str | None = None
    error: str | None = None

    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def succeeded(
        cls,
        *,
        data: Any = None,
        message: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "ActionResult":
        return cls(
            success=True,
            data=data,
            message=message,
            metadata=metadata or {},
        )

    @classmethod
    def failed(
        cls,
        *,
        error: str,
        data: Any = None,
        metadata: dict[str, Any] | None = None,
    ) -> "ActionResult":
        return cls(
            success=False,
            data=data,
            error=error,
            metadata=metadata or {},
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "data": self.data,
            "message": self.message,
            "error": self.error,
            "metadata": self.metadata,
        }


class BaseAction(ABC):
    """
    Base class for every Baby automation action.

    Each plugin must provide a unique `name` and implement `execute`.
    """

    name: str = ""
    description: str = ""

    def validate_arguments(
        self,
        arguments: dict[str, Any],
    ) -> None:
        """
        Override this method when an action needs custom validation.
        """
        if not isinstance(arguments, dict):
            raise TypeError("Action arguments must be a dictionary.")

    @abstractmethod
    async def execute(
        self,
        arguments: dict[str, Any],
        context: ActionContext,
    ) -> ActionResult:
        """
        Execute the action.
        """
        raise NotImplementedError