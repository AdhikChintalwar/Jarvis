from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from core.automation.automation_executor import (
    AutomationExecutionResult,
    AutomationExecutor,
)
from core.automation.automation_store import (
    AutomationStore,
)
from core.automation.models import Automation
from core.automation.scheduler import (
    AutomationScheduler,
    RuntimeDataProvider,
)
from core.automation.trigger_engine import (
    TriggerEngine,
)


class AutomationManager:
    """
    High-level facade for Baby's automation system.

    Use this class from the voice assistant, CLI, GUI, or API.
    """

    def __init__(
        self,
        *,
        database_path: str | Path = (
            "data/baby_automations.db"
        ),
        poll_interval_seconds: float = 1.0,
        refresh_interval_seconds: float = 10.0,
        runtime_data_provider: (
            RuntimeDataProvider | None
        ) = None,
    ) -> None:
        self.store = AutomationStore(
            database_path=database_path
        )

        self.trigger_engine = TriggerEngine()

        self.executor = AutomationExecutor(
            store=self.store
        )

        self.scheduler = AutomationScheduler(
            store=self.store,
            executor=self.executor,
            trigger_engine=self.trigger_engine,
            poll_interval_seconds=(
                poll_interval_seconds
            ),
            refresh_interval_seconds=(
                refresh_interval_seconds
            ),
            runtime_data_provider=(
                runtime_data_provider
            ),
        )

    async def start(self) -> None:
        await self.scheduler.start()

    async def stop(self) -> None:
        await self.scheduler.stop()

    async def create(
        self,
        automation: Automation,
    ) -> Automation:
        automation.validate()

        evaluation = (
            self.trigger_engine.calculate_next_run(
                automation
            )
        )

        if not evaluation.supported:
            raise ValueError(
                evaluation.error
                or "Invalid automation trigger."
            )

        automation.next_run = evaluation.next_run

        saved = self.store.save(
            automation
        )

        await self.scheduler.refresh()

        return saved

    async def update(
        self,
        automation: Automation,
    ) -> Automation:
        return await self.create(automation)

    async def delete(
        self,
        automation_id: str,
    ) -> bool:
        deleted = self.store.delete(
            automation_id
        )

        await self.scheduler.refresh()

        return deleted

    async def enable(
        self,
        automation_id: str,
    ) -> Automation:
        automation = self.store.get_required(
            automation_id
        )

        automation.enabled = True

        evaluation = (
            self.trigger_engine.calculate_next_run(
                automation
            )
        )

        if not evaluation.supported:
            raise ValueError(
                evaluation.error
                or "Invalid automation trigger."
            )

        automation.next_run = evaluation.next_run

        self.store.save(automation)
        await self.scheduler.refresh()

        return automation

    async def disable(
        self,
        automation_id: str,
    ) -> Automation:
        automation = self.store.set_enabled(
            automation_id,
            False,
        )

        automation.next_run = None
        self.store.save(automation)

        await self.scheduler.refresh()

        return automation

    async def pause(
        self,
        automation_id: str,
    ) -> Automation:
        automation = self.store.get_required(
            automation_id
        )

        automation.pause()
        automation.next_run = None

        self.store.save(automation)
        await self.scheduler.refresh()

        return automation

    async def resume(
        self,
        automation_id: str,
    ) -> Automation:
        automation = self.store.get_required(
            automation_id
        )

        automation.resume()

        evaluation = (
            self.trigger_engine.calculate_next_run(
                automation
            )
        )

        if not evaluation.supported:
            raise ValueError(
                evaluation.error
                or "Invalid automation trigger."
            )

        automation.next_run = evaluation.next_run

        self.store.save(automation)
        await self.scheduler.refresh()

        return automation

    async def run_now(
        self,
        automation_id: str,
        *,
        runtime_data: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AutomationExecutionResult:
        return await self.scheduler.run_now(
            automation_id,
            runtime_data=runtime_data,
            metadata=metadata,
        )

    def get(
        self,
        automation_id: str,
    ) -> Automation | None:
        return self.store.get(
            automation_id
        )

    def list_all(self) -> list[Automation]:
        return self.store.list_all()

    def list_enabled(self) -> list[Automation]:
        return self.store.list_enabled()

    def history(
        self,
        *,
        automation_id: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        return self.store.list_run_history(
            automation_id=automation_id,
            limit=limit,
        )

    def next_run(
        self,
        automation_id: str,
    ) -> datetime | None:
        automation = self.store.get_required(
            automation_id
        )
        return automation.next_run

    async def __aenter__(
        self,
    ) -> "AutomationManager":
        await self.start()
        return self

    async def __aexit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: Any,
    ) -> None:
        await self.stop()
        self.store.close()