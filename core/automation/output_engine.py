from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Any

from core.automation.models import Automation
from core.automation.outputs.base_output import (
    OutputContext,
    OutputResult,
)
from core.automation.outputs.output_registry import (
    OutputRegistry,
    output_registry,
)


@dataclass
class OutputPipelineResult:
    """
    Complete result from delivering all automation outputs.
    """

    success: bool
    output_results: list[OutputResult] = field(
        default_factory=list
    )

    failed_output_indexes: list[int] = field(
        default_factory=list
    )
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "output_results": [
                result.to_dict()
                for result in self.output_results
            ],
            "failed_output_indexes": self.failed_output_indexes,
            "errors": self.errors,
        }


class OutputEngine:
    """
    Delivers automation results through registered output plugins.
    """

    def __init__(
        self,
        registry: OutputRegistry | None = None,
    ) -> None:
        self.registry = registry or output_registry

    async def deliver_outputs(
        self,
        automation: Automation,
        *,
        action_state: dict[str, Any],
        action_result: Any = None,
        condition_result: Any = None,
        metadata: dict[str, Any] | None = None,
        stop_on_failure: bool = False,
    ) -> OutputPipelineResult:
        automation.validate()

        output_results: list[OutputResult] = []
        failed_indexes: list[int] = []
        errors: list[str] = []

        execution_metadata = dict(metadata or {})

        enabled_outputs = [
            output
            for output in automation.outputs
            if output.enabled
        ]

        for index, output_definition in enumerate(
            enabled_outputs
        ):
            output_type = output_definition.type

            try:
                output_plugin = self.registry.get_required(
                    output_type
                )

                output_plugin.validate_config(
                    output_definition.config
                )

                context = OutputContext(
                    automation=automation,
                    output_index=index,
                    action_state=action_state,
                    action_result=action_result,
                    condition_result=condition_result,
                    metadata=execution_metadata,
                )

                result = output_plugin.deliver(
                    output_definition.config,
                    context,
                )

                if inspect.isawaitable(result):
                    result = await result

                if not isinstance(result, OutputResult):
                    raise TypeError(
                        f"Output '{output_type}' returned "
                        f"{type(result).__name__}, but an "
                        "OutputResult was required."
                    )

            except Exception as error:
                result = OutputResult.failed(
                    output_type=output_type,
                    error=str(error),
                    metadata={
                        "output_index": index,
                    },
                )

            output_results.append(result)

            if not result.success:
                failed_indexes.append(index)
                errors.append(
                    result.error
                    or f"Output failed: {output_type}"
                )

                if stop_on_failure:
                    break

        return OutputPipelineResult(
            success=len(failed_indexes) == 0,
            output_results=output_results,
            failed_output_indexes=failed_indexes,
            errors=errors,
        )