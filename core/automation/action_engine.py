from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Any

from core.automation.actions.action_registry import (
    ActionRegistry,
    action_registry,
)
from core.automation.actions.base_action import (
    ActionContext,
    ActionResult,
)
from core.automation.models import Automation


@dataclass
class ActionPipelineResult:
    """
    Complete result from running an automation's action pipeline.
    """

    success: bool
    action_results: list[ActionResult] = field(default_factory=list)
    state: dict[str, Any] = field(default_factory=dict)

    failed_action_index: int | None = None
    failed_action_name: str | None = None
    error: str | None = None

    @property
    def final_result(self) -> ActionResult | None:
        if not self.action_results:
            return None

        return self.action_results[-1]

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "action_results": [
                result.to_dict()
                for result in self.action_results
            ],
            "state": self.state,
            "failed_action_index": self.failed_action_index,
            "failed_action_name": self.failed_action_name,
            "error": self.error,
        }


class ActionEngine:
    """
    Executes action plugins registered with the ActionRegistry.

    The engine does not know how reminders, stocks, weather, browser
    actions, or other capabilities are implemented.
    """

    def __init__(
        self,
        registry: ActionRegistry | None = None,
    ) -> None:
        self.registry = registry or action_registry

    async def execute_automation(
        self,
        automation: Automation,
        *,
        initial_state: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        stop_on_failure: bool = True,
    ) -> ActionPipelineResult:
        """
        Run every action in an automation sequentially.
        """
        automation.validate()

        state = dict(initial_state or {})
        execution_metadata = dict(metadata or {})

        action_results: list[ActionResult] = []
        previous_result: Any = None

        for index, action_definition in enumerate(
            automation.actions
        ):
            action_name = action_definition.name

            try:
                action_plugin = self.registry.get_required(
                    action_name
                )

                action_plugin.validate_arguments(
                    action_definition.arguments
                )

                context = ActionContext(
                    automation=automation,
                    action_index=index,
                    state=state,
                    previous_result=previous_result,
                    metadata=execution_metadata,
                )

                result = action_plugin.execute(
                    action_definition.arguments,
                    context,
                )

                if inspect.isawaitable(result):
                    result = await result

                if not isinstance(result, ActionResult):
                    raise TypeError(
                        f"Action '{action_name}' returned "
                        f"{type(result).__name__}, but an "
                        "ActionResult was required."
                    )

            except Exception as error:
                failed_result = ActionResult.failed(
                    error=str(error),
                    metadata={
                        "action_name": action_name,
                        "action_index": index,
                    },
                )

                action_results.append(failed_result)

                state["last_error"] = str(error)
                state["failed_action"] = action_name

                if stop_on_failure:
                    return ActionPipelineResult(
                        success=False,
                        action_results=action_results,
                        state=state,
                        failed_action_index=index,
                        failed_action_name=action_name,
                        error=str(error),
                    )

                previous_result = failed_result.data
                continue

            action_results.append(result)

            result_key = f"action_{index}"
            state[result_key] = result.data
            state["last_result"] = result.data
            state["last_action"] = action_name

            previous_result = result.data

            if not result.success:
                state["last_error"] = result.error
                state["failed_action"] = action_name

                if stop_on_failure:
                    return ActionPipelineResult(
                        success=False,
                        action_results=action_results,
                        state=state,
                        failed_action_index=index,
                        failed_action_name=action_name,
                        error=result.error,
                    )

        return ActionPipelineResult(
            success=all(
                result.success
                for result in action_results
            ),
            action_results=action_results,
            state=state,
        )