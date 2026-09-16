from __future__ import annotations

import asyncio
import inspect
import logging
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from core.automation.automation_executor import (
    AutomationExecutionResult,
    AutomationExecutor,
)
from core.automation.automation_store import (
    AutomationStore,
)
from core.automation.models import Automation
from core.automation.trigger_engine import (
    TriggerEngine,
)


RuntimeDataProvider = Callable[
    [Automation],
    dict[str, Any]
    | Awaitable[dict[str, Any]],
]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AutomationScheduler:
    """
    Async scheduler for Baby automations.

    The scheduler:

    - loads enabled automations from SQLite
    - calculates missing next-run times
    - checks when automations become due
    - calls AutomationExecutor.execute()
    - updates the next scheduled run
    - avoids running the same automation concurrently
    - periodically reloads automations from SQLite
    """

    def __init__(
        self,
        *,
        store: AutomationStore,
        executor: AutomationExecutor,
        trigger_engine: TriggerEngine | None = None,
        poll_interval_seconds: float = 1.0,
        refresh_interval_seconds: float = 10.0,
        runtime_data_provider: (
            RuntimeDataProvider | None
        ) = None,
        logger: logging.Logger | None = None,
    ) -> None:
        if poll_interval_seconds <= 0:
            raise ValueError(
                "poll_interval_seconds must be positive."
            )

        if refresh_interval_seconds <= 0:
            raise ValueError(
                "refresh_interval_seconds must be positive."
            )

        self.store = store
        self.executor = executor
        self.trigger_engine = (
            trigger_engine or TriggerEngine()
        )

        self.poll_interval_seconds = float(
            poll_interval_seconds
        )
        self.refresh_interval_seconds = float(
            refresh_interval_seconds
        )

        self.runtime_data_provider = (
            runtime_data_provider
        )

        self.logger = logger or logging.getLogger(
            __name__
        )

        self._automations: dict[
            str,
            Automation,
        ] = {}

        self._running_tasks: dict[
            str,
            asyncio.Task[
                AutomationExecutionResult
            ],
        ] = {}

        self._main_task: (
            asyncio.Task[None] | None
        ) = None

        self._stop_event = asyncio.Event()
        self._started = False
        self._last_refresh: (
            datetime | None
        ) = None

    @property
    def is_running(self) -> bool:
        return (
            self._started
            and self._main_task is not None
            and not self._main_task.done()
        )

    @property
    def loaded_automation_count(self) -> int:
        return len(self._automations)

    @property
    def running_automation_count(self) -> int:
        return len(self._running_tasks)

    async def start(self) -> None:
        """
        Start the scheduler in the background.
        """
        if self.is_running:
            return

        self._stop_event.clear()

        await self.refresh()

        self._started = True
        self._main_task = asyncio.create_task(
            self.run_forever(),
            name="baby-automation-scheduler",
        )

        self.logger.info(
            "Automation scheduler started."
        )

    async def run_forever(self) -> None:
        """
        Run the scheduling loop until stop() is called.

        This can also be called directly instead of start().
        """
        if not self._started:
            self._started = True
            self._stop_event.clear()
            await self.refresh()

        try:
            while not self._stop_event.is_set():
                await self.tick()

                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(),
                        timeout=(
                            self.poll_interval_seconds
                        ),
                    )
                except asyncio.TimeoutError:
                    pass

        except asyncio.CancelledError:
            raise

        finally:
            self._started = False
            self.logger.info(
                "Automation scheduler loop stopped."
            )

    async def stop(
        self,
        *,
        wait_for_running: bool = True,
    ) -> None:
        """
        Stop scheduling new executions.

        When wait_for_running=True, currently executing automations
        are allowed to finish.
        """
        self._stop_event.set()

        current_task = asyncio.current_task()

        if (
            self._main_task is not None
            and self._main_task is not current_task
            and not self._main_task.done()
        ):
            try:
                await self._main_task
            except asyncio.CancelledError:
                pass

        if wait_for_running:
            running_tasks = list(
                self._running_tasks.values()
            )

            if running_tasks:
                await asyncio.gather(
                    *running_tasks,
                    return_exceptions=True,
                )
        else:
            for task in list(
                self._running_tasks.values()
            ):
                task.cancel()

        self._main_task = None
        self._started = False

        self.logger.info(
            "Automation scheduler stopped."
        )

    async def tick(self) -> None:
        """
        Perform one scheduler cycle.
        """
        await self._refresh_if_needed()
        self._clean_finished_tasks()

        current_time = utc_now()

        for automation in list(
            self._automations.values()
        ):
            if not self._is_eligible(
                automation
            ):
                continue

            if automation.id in self._running_tasks:
                continue

            if automation.next_run is None:
                await self._initialize_next_run(
                    automation,
                    current_time,
                )
                continue

            if not self.trigger_engine.is_due(
                automation,
                now=current_time,
            ):
                continue

            task = asyncio.create_task(
                self._execute_due_automation(
                    automation
                ),
                name=(
                    f"baby-automation-"
                    f"{automation.id}"
                ),
            )

            self._running_tasks[
                automation.id
            ] = task

    async def refresh(self) -> None:
        """
        Reload enabled automations from SQLite.
        """
        automations = await asyncio.to_thread(
            self.store.list_enabled
        )

        refreshed: dict[str, Automation] = {}

        for automation in automations:
            refreshed[automation.id] = automation

        self._automations = refreshed
        self._last_refresh = utc_now()

        self.logger.debug(
            "Loaded %s enabled automations.",
            len(refreshed),
        )

    async def run_now(
        self,
        automation_id: str,
        *,
        runtime_data: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AutomationExecutionResult:
        """
        Execute an automation immediately, regardless of its trigger.
        """
        if automation_id in self._running_tasks:
            raise RuntimeError(
                f"Automation is already running: "
                f"{automation_id}"
            )

        automation = await asyncio.to_thread(
            self.store.get_required,
            automation_id,
        )

        supplied_metadata = {
            **(metadata or {}),
            "trigger_source": (
                metadata or {}
            ).get(
                "trigger_source",
                "manual",
            ),
        }

        resolved_runtime_data = (
            runtime_data
            if runtime_data is not None
            else await self._get_runtime_data(
                automation
            )
        )

        result = await self.executor.execute(
            automation,
            runtime_data=resolved_runtime_data,
            metadata=supplied_metadata,
        )

        return result

    async def _refresh_if_needed(self) -> None:
        if self._last_refresh is None:
            await self.refresh()
            return

        elapsed = (
            utc_now() - self._last_refresh
        ).total_seconds()

        if elapsed >= self.refresh_interval_seconds:
            await self.refresh()

    async def _initialize_next_run(
        self,
        automation: Automation,
        current_time: datetime,
    ) -> None:
        evaluation = (
            self.trigger_engine.calculate_next_run(
                automation,
                from_time=current_time,
            )
        )

        if not evaluation.supported:
            self.logger.warning(
                "Could not schedule automation %s: %s",
                automation.id,
                evaluation.error,
            )
            return

        if evaluation.next_run is None:
            return

        automation.next_run = evaluation.next_run

        await asyncio.to_thread(
            self.store.update_next_run_time,
            automation.id,
            evaluation.next_run,
        )

        self._automations[
            automation.id
        ] = automation

        self.logger.debug(
            "Initialized next run for %s at %s.",
            automation.id,
            evaluation.next_run.isoformat(),
        )

    async def _execute_due_automation(
        self,
        automation: Automation,
    ) -> AutomationExecutionResult:
        try:
            runtime_data = await self._get_runtime_data(
                automation
            )

            result = await self.executor.execute(
                automation,
                runtime_data=runtime_data,
                metadata={
                    "trigger_source": "scheduler",
                    "scheduled_for": (
                        automation.next_run.isoformat()
                        if automation.next_run
                        else None
                    ),
                },
            )

            await self._schedule_following_run(
                automation,
                result,
            )

            return result

        except Exception:
            self.logger.exception(
                "Unhandled scheduler failure for "
                "automation %s.",
                automation.id,
            )
            raise

        finally:
            self._running_tasks.pop(
                automation.id,
                None,
            )

    async def _schedule_following_run(
        self,
        automation: Automation,
        result: AutomationExecutionResult,
    ) -> None:
        trigger_type = (
            self.trigger_engine.get_trigger_type(
                automation
            )
        )

        next_run = (
            self.trigger_engine.calculate_after_execution(
                automation,
                executed_at=result.finished_at,
            )
        )

        automation.next_run = next_run

        if trigger_type in {"once", "date"}:
            automation.enabled = False

            await asyncio.to_thread(
                self.store.save,
                automation,
            )

            self._automations.pop(
                automation.id,
                None,
            )

            self.logger.info(
                "One-time automation %s completed "
                "and was disabled.",
                automation.id,
            )

            return

        await asyncio.to_thread(
            self.store.update_next_run_time,
            automation.id,
            next_run,
        )

        if next_run is not None:
            self._automations[
                automation.id
            ] = automation

            self.logger.debug(
                "Next run for %s scheduled at %s.",
                automation.id,
                next_run.isoformat(),
            )

    async def _get_runtime_data(
        self,
        automation: Automation,
    ) -> dict[str, Any]:
        if self.runtime_data_provider is None:
            return {}

        result = self.runtime_data_provider(
            automation
        )

        if inspect.isawaitable(result):
            result = await result

        if result is None:
            return {}

        if not isinstance(result, dict):
            raise TypeError(
                "Runtime data provider must return "
                "a dictionary."
            )

        return dict(result)

    def _clean_finished_tasks(self) -> None:
        finished_ids = [
            automation_id
            for automation_id, task
            in self._running_tasks.items()
            if task.done()
        ]

        for automation_id in finished_ids:
            task = self._running_tasks.pop(
                automation_id
            )

            if task.cancelled():
                continue

            exception = task.exception()

            if exception is not None:
                self.logger.error(
                    "Automation task %s failed: %s",
                    automation_id,
                    exception,
                )

    @staticmethod
    def _is_eligible(
        automation: Automation,
    ) -> bool:
        if not getattr(
            automation,
            "enabled",
            False,
        ):
            return False

        status = getattr(
            automation,
            "status",
            "active",
        )

        status_value = getattr(
            status,
            "value",
            status,
        )

        return (
            isinstance(status_value, str)
            and status_value.strip().lower()
            == "active"
        )