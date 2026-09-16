from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from core.automation.action_engine import (
    ActionEngine,
    ActionPipelineResult,
)
from core.automation.automation_store import AutomationStore
from core.automation.condition_engine import (
    ConditionEngine,
    ConditionPipelineResult,
)
from core.automation.models import Automation
from core.automation.output_engine import (
    OutputEngine,
    OutputPipelineResult,
)


def utc_now() -> datetime:
    """Return the current timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


class ExecutionStatus(str, Enum):
    """Final status of an automation execution."""

    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class ExecutionPhase(str, Enum):
    """Phase at which the automation execution stopped."""

    CONDITIONS = "conditions"
    ACTIONS = "actions"
    OUTPUTS = "outputs"
    COMPLETED = "completed"


@dataclass
class AutomationExecutionResult:
    """Complete result produced by AutomationExecutor."""

    automation_id: str
    automation_name: str

    status: ExecutionStatus
    stopped_at_phase: ExecutionPhase

    started_at: datetime
    finished_at: datetime

    condition_result: ConditionPipelineResult | None = None
    action_result: ActionPipelineResult | None = None
    output_result: OutputPipelineResult | None = None

    runtime_data: dict[str, Any] = field(
        default_factory=dict
    )
    error: str | None = None
    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    @property
    def success(self) -> bool:
        return self.status == ExecutionStatus.SUCCESS

    @property
    def skipped(self) -> bool:
        return self.status == ExecutionStatus.SKIPPED

    @property
    def duration_seconds(self) -> float:
        return max(
            0.0,
            (
                self.finished_at - self.started_at
            ).total_seconds(),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "automation_id": self.automation_id,
            "automation_name": self.automation_name,
            "status": self.status.value,
            "success": self.success,
            "skipped": self.skipped,
            "stopped_at_phase": (
                self.stopped_at_phase.value
            ),
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat(),
            "duration_seconds": self.duration_seconds,
            "condition_result": (
                self.condition_result.to_dict()
                if self.condition_result is not None
                else None
            ),
            "action_result": (
                self.action_result.to_dict()
                if self.action_result is not None
                else None
            ),
            "output_result": (
                self.output_result.to_dict()
                if self.output_result is not None
                else None
            ),
            "runtime_data": self.runtime_data,
            "error": self.error,
            "metadata": self.metadata,
        }


class AutomationExecutor:
    """
    Central orchestrator for executing Baby automations.

    Execution order:

        1. Validate automation
        2. Create run-history record
        3. Evaluate conditions
        4. Execute actions
        5. Deliver outputs
        6. Finish run-history record
        7. Update automation statistics

    The scheduler, voice assistant, UI, API, and manual commands
    should call this executor instead of invoking individual engines.
    """

    def __init__(
        self,
        *,
        condition_engine: ConditionEngine | None = None,
        action_engine: ActionEngine | None = None,
        output_engine: OutputEngine | None = None,
        store: AutomationStore | None = None,
    ) -> None:
        self.condition_engine = (
            condition_engine or ConditionEngine()
        )
        self.action_engine = (
            action_engine or ActionEngine()
        )
        self.output_engine = (
            output_engine or OutputEngine()
        )
        self.store = store

    async def execute(
        self,
        automation: Automation,
        *,
        runtime_data: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        condition_mode: str | None = None,
        stop_outputs_on_failure: bool = False,
    ) -> AutomationExecutionResult:
        """
        Execute one automation from beginning to end.

        Persistence is enabled when an AutomationStore was supplied
        to the constructor.
        """
        started_at = utc_now()
        runtime_state = dict(runtime_data or {})
        execution_metadata = dict(metadata or {})

        run_id: int | None = None
        condition_result: ConditionPipelineResult | None = None
        action_result: ActionPipelineResult | None = None
        output_result: OutputPipelineResult | None = None

        current_phase = ExecutionPhase.CONDITIONS

        try:
            automation.validate()

            selected_condition_mode = (
                self._resolve_condition_mode(
                    automation=automation,
                    explicit_mode=condition_mode,
                )
            )

            run_id = await self._create_run_record(
                automation=automation,
                started_at=started_at,
                runtime_data=runtime_state,
                metadata=execution_metadata,
            )

            result_metadata = {
                **execution_metadata,
                "run_id": run_id,
            }

            # -------------------------------------------------
            # Phase 1: Conditions
            # -------------------------------------------------

            current_phase = ExecutionPhase.CONDITIONS

            condition_result = (
                self.condition_engine.evaluate_all(
                    automation.conditions,
                    runtime_state,
                    mode=selected_condition_mode,
                )
            )

            if not condition_result.passed:
                result = AutomationExecutionResult(
                    automation_id=automation.id,
                    automation_name=automation.name,
                    status=ExecutionStatus.SKIPPED,
                    stopped_at_phase=(
                        ExecutionPhase.CONDITIONS
                    ),
                    started_at=started_at,
                    finished_at=utc_now(),
                    condition_result=condition_result,
                    runtime_data=runtime_state,
                    metadata=result_metadata,
                )

                await self._persist_finished_result(
                    run_id=run_id,
                    automation=automation,
                    result=result,
                )

                return result

            # -------------------------------------------------
            # Phase 2: Actions
            # -------------------------------------------------

            current_phase = ExecutionPhase.ACTIONS

            action_result = (
                await self.action_engine.execute_automation(
                    automation
                )
            )

            if not action_result.success:
                result = AutomationExecutionResult(
                    automation_id=automation.id,
                    automation_name=automation.name,
                    status=ExecutionStatus.FAILED,
                    stopped_at_phase=(
                        ExecutionPhase.ACTIONS
                    ),
                    started_at=started_at,
                    finished_at=utc_now(),
                    condition_result=condition_result,
                    action_result=action_result,
                    runtime_data=runtime_state,
                    error=self._get_action_error(
                        action_result
                    ),
                    metadata=result_metadata,
                )

                await self._persist_finished_result(
                    run_id=run_id,
                    automation=automation,
                    result=result,
                )

                return result

            # -------------------------------------------------
            # Phase 3: Outputs
            # -------------------------------------------------

            current_phase = ExecutionPhase.OUTPUTS

            output_result = (
                await self.output_engine.deliver_outputs(
                    automation,
                    action_state=action_result.state,
                    action_result=action_result,
                    condition_result=condition_result,
                    metadata=execution_metadata,
                    stop_on_failure=(
                        stop_outputs_on_failure
                    ),
                )
            )

            if not output_result.success:
                result = AutomationExecutionResult(
                    automation_id=automation.id,
                    automation_name=automation.name,
                    status=ExecutionStatus.FAILED,
                    stopped_at_phase=(
                        ExecutionPhase.OUTPUTS
                    ),
                    started_at=started_at,
                    finished_at=utc_now(),
                    condition_result=condition_result,
                    action_result=action_result,
                    output_result=output_result,
                    runtime_data=runtime_state,
                    error=self._combine_output_errors(
                        output_result
                    ),
                    metadata=result_metadata,
                )

                await self._persist_finished_result(
                    run_id=run_id,
                    automation=automation,
                    result=result,
                )

                return result

            # -------------------------------------------------
            # Completed successfully
            # -------------------------------------------------

            current_phase = ExecutionPhase.COMPLETED

            result = AutomationExecutionResult(
                automation_id=automation.id,
                automation_name=automation.name,
                status=ExecutionStatus.SUCCESS,
                stopped_at_phase=ExecutionPhase.COMPLETED,
                started_at=started_at,
                finished_at=utc_now(),
                condition_result=condition_result,
                action_result=action_result,
                output_result=output_result,
                runtime_data=runtime_state,
                metadata=result_metadata,
            )

            await self._persist_finished_result(
                run_id=run_id,
                automation=automation,
                result=result,
            )

            return result

        except Exception as error:
            result = self._failed_result(
                automation=automation,
                started_at=started_at,
                stopped_at_phase=current_phase,
                condition_result=condition_result,
                action_result=action_result,
                output_result=output_result,
                runtime_data=runtime_state,
                metadata={
                    **execution_metadata,
                    "run_id": run_id,
                },
                error=str(error),
            )

            await self._persist_finished_result(
                run_id=run_id,
                automation=automation,
                result=result,
            )

            return result

    # ---------------------------------------------------------
    # Persistence
    # ---------------------------------------------------------

    async def _create_run_record(
        self,
        *,
        automation: Automation,
        started_at: datetime,
        runtime_data: dict[str, Any],
        metadata: dict[str, Any],
    ) -> int | None:
        """Create a run-history record when persistence is enabled."""
        if self.store is None:
            return None

        trigger_source = metadata.get(
            "trigger_source",
            "unknown",
        )

        return await asyncio.to_thread(
            self.store.create_run_record,
            automation_id=automation.id,
            status="running",
            trigger_source=str(trigger_source),
            runtime_data=runtime_data,
            metadata=metadata,
            started_at=started_at,
        )

    async def _persist_finished_result(
        self,
        *,
        run_id: int | None,
        automation: Automation,
        result: AutomationExecutionResult,
    ) -> None:
        """
        Finish run history and update execution statistics.

        A persistence failure is attached to result.metadata rather
        than replacing the actual automation execution result.
        """
        if self.store is None:
            return

        try:
            if run_id is not None:
                await asyncio.to_thread(
                    self.store.finish_run_record,
                    run_id,
                    status=result.status.value,
                    stopped_at_phase=(
                        result.stopped_at_phase.value
                    ),
                    result=result.to_dict(),
                    error=result.error,
                    finished_at=result.finished_at,
                )

            await asyncio.to_thread(
                self.store.update_execution_statistics,
                automation.id,
                last_run=result.finished_at,
                increment_run_count=True,
            )

            automation.last_run = result.finished_at
            automation.run_count = int(
                automation.run_count or 0
            ) + 1
            automation.updated_at = result.finished_at

        except Exception as persistence_error:
            result.metadata["persistence_error"] = str(
                persistence_error
            )

    # ---------------------------------------------------------
    # Condition settings
    # ---------------------------------------------------------

    @staticmethod
    def _resolve_condition_mode(
        *,
        automation: Automation,
        explicit_mode: str | None,
    ) -> str:
        mode = explicit_mode

        if mode is None:
            mode = automation.metadata.get(
                "condition_mode",
                "all",
            )

        if not isinstance(mode, str):
            raise TypeError(
                "Condition mode must be a string."
            )

        normalized = mode.strip().lower()

        if normalized not in {"all", "any"}:
            raise ValueError(
                "Condition mode must be 'all' or 'any'."
            )

        return normalized

    # ---------------------------------------------------------
    # Error extraction
    # ---------------------------------------------------------

    @staticmethod
    def _get_action_error(
        action_result: ActionPipelineResult,
    ) -> str:
        """Extract the most useful error from an action pipeline."""
        direct_error = getattr(
            action_result,
            "error",
            None,
        )

        if direct_error:
            return str(direct_error)

        action_results = getattr(
            action_result,
            "action_results",
            [],
        )

        for result in action_results:
            if not getattr(result, "success", True):
                error = getattr(
                    result,
                    "error",
                    None,
                )

                if error:
                    return str(error)

                message = getattr(
                    result,
                    "message",
                    None,
                )

                if message:
                    return str(message)

        failed_name = getattr(
            action_result,
            "failed_action_name",
            None,
        )

        failed_index = getattr(
            action_result,
            "failed_action_index",
            None,
        )

        if failed_name is not None:
            message = f"Action '{failed_name}' failed"

            if failed_index is not None:
                message += f" at index {failed_index}"

            return message + "."

        if failed_index is not None:
            return (
                f"Automation action at index "
                f"{failed_index} failed."
            )

        return "One or more automation actions failed."

    @staticmethod
    def _combine_output_errors(
        output_result: OutputPipelineResult,
    ) -> str:
        """Combine all output errors into one message."""
        errors = getattr(
            output_result,
            "errors",
            [],
        )

        cleaned_errors = [
            str(error)
            for error in errors
            if error
        ]

        if cleaned_errors:
            return "; ".join(cleaned_errors)

        output_results = getattr(
            output_result,
            "output_results",
            [],
        )

        for result in output_results:
            if not getattr(result, "success", True):
                error = getattr(
                    result,
                    "error",
                    None,
                )

                if error:
                    cleaned_errors.append(str(error))

        if cleaned_errors:
            return "; ".join(cleaned_errors)

        return "One or more automation outputs failed."

    # ---------------------------------------------------------
    # Failure-result helper
    # ---------------------------------------------------------

    @staticmethod
    def _failed_result(
        *,
        automation: Automation,
        started_at: datetime,
        stopped_at_phase: ExecutionPhase,
        runtime_data: dict[str, Any],
        metadata: dict[str, Any],
        error: str,
        condition_result: (
            ConditionPipelineResult | None
        ) = None,
        action_result: ActionPipelineResult | None = None,
        output_result: OutputPipelineResult | None = None,
    ) -> AutomationExecutionResult:
        """Build a standardized failed execution result."""
        return AutomationExecutionResult(
            automation_id=getattr(
                automation,
                "id",
                "unknown",
            ),
            automation_name=getattr(
                automation,
                "name",
                "Unknown automation",
            ),
            status=ExecutionStatus.FAILED,
            stopped_at_phase=stopped_at_phase,
            started_at=started_at,
            finished_at=utc_now(),
            condition_result=condition_result,
            action_result=action_result,
            output_result=output_result,
            runtime_data=runtime_data,
            error=error,
            metadata=metadata,
        )