from __future__ import annotations

import asyncio
import threading
from concurrent.futures import Future
from typing import Any

from voice.tts import speak
from voice.wake_engine import OpenWakeWordEngine

from core.session_manager import start_session
from core.event_handlers import register_event_handlers
from core.event_bus import publish

from core.automation import (
    AutomationManager,
    register_builtin_actions,
    register_builtin_outputs,
)


class AutomationRuntime:
    """
    Runs Baby's asynchronous automation system in a dedicated
    background thread and asyncio event loop.

    This allows the synchronous wake-word loop to continue running
    on the main thread.
    """

    def __init__(self) -> None:
        self.manager: AutomationManager | None = None

        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()
        self._startup_error: BaseException | None = None

    def start(self) -> None:
        """
        Start the automation event loop and scheduler.
        """
        if self.is_running:
            return

        self._ready.clear()
        self._startup_error = None

        self._thread = threading.Thread(
            target=self._run_event_loop,
            name="baby-automation-runtime",
            daemon=True,
        )
        self._thread.start()

        # Wait until the manager has started or failed.
        if not self._ready.wait(timeout=10):
            raise TimeoutError(
                "Automation runtime did not start within 10 seconds."
            )

        if self._startup_error is not None:
            raise RuntimeError(
                "Automation runtime failed to start."
            ) from self._startup_error

        print("Automation runtime started.")

    def stop(self) -> None:
        """
        Stop the automation scheduler and background event loop.
        """
        if self._loop is None or self.manager is None:
            return

        if not self._loop.is_running():
            return

        future = asyncio.run_coroutine_threadsafe(
            self._shutdown(),
            self._loop,
        )

        try:
            future.result(timeout=15)
        except Exception as error:
            print(
                "Automation runtime shutdown error:",
                error,
            )

        if (
            self._thread is not None
            and self._thread.is_alive()
        ):
            self._thread.join(timeout=5)

        self._thread = None
        self._loop = None
        self.manager = None

        print("Automation runtime stopped.")

    def run_automation_now(
        self,
        automation_id: str,
        *,
        runtime_data: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Future:
        """
        Submit a manual automation execution from synchronous code.

        The returned Future can be inspected with future.result().
        """
        if (
            self._loop is None
            or self.manager is None
            or not self._loop.is_running()
        ):
            raise RuntimeError(
                "Automation runtime is not running."
            )

        return asyncio.run_coroutine_threadsafe(
            self.manager.run_now(
                automation_id,
                runtime_data=runtime_data,
                metadata=metadata,
            ),
            self._loop,
        )

    @property
    def is_running(self) -> bool:
        return (
            self._thread is not None
            and self._thread.is_alive()
            and self._loop is not None
            and self._loop.is_running()
        )

    def _run_event_loop(self) -> None:
        """
        Thread target that owns the automation asyncio loop.
        """
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        self._loop = loop

        try:
            loop.run_until_complete(
                self._start_manager()
            )
        except BaseException as error:
            self._startup_error = error
            self._ready.set()
            loop.close()
            return

        self._ready.set()

        try:
            loop.run_forever()
        finally:
            pending_tasks = asyncio.all_tasks(loop)

            for task in pending_tasks:
                task.cancel()

            if pending_tasks:
                loop.run_until_complete(
                    asyncio.gather(
                        *pending_tasks,
                        return_exceptions=True,
                    )
                )

            loop.run_until_complete(
                loop.shutdown_asyncgens()
            )
            loop.close()

    async def _start_manager(self) -> None:
        """
        Construct and start the automation manager inside its
        owning event loop.
        """
        register_builtin_actions()
        register_builtin_outputs()

        self.manager = AutomationManager(
            database_path="data/baby_automations.db",
            poll_interval_seconds=1.0,
            refresh_interval_seconds=5.0,
        )

        await self.manager.start()

    async def _shutdown(self) -> None:
        """
        Stop the manager, close its database, and stop the loop.
        """
        try:
            if self.manager is not None:
                await self.manager.stop()
                self.manager.store.close()
        finally:
            if self._loop is not None:
                self._loop.stop()


automation_runtime = AutomationRuntime()


def start_baby() -> None:
    wake_engine: OpenWakeWordEngine | None = None

    try:
        print("Starting Baby...")

        register_event_handlers()

        # Starts the new SQLite-backed automation scheduler.
        automation_runtime.start()

        wake_engine = OpenWakeWordEngine()

        speak("I'm back baby")
        publish("app_started")

        print("Baby is listening for the wake word.")

        while True:
            wake_engine.wait_for_wake_word()

            start_session(speak)

            print(
                "Session closed. Returning to wake mode."
            )

    except KeyboardInterrupt:
        print("\nShutting down Baby...")

    except Exception as error:
        print(
            "\nBaby encountered an error:",
            error,
        )
        raise

    finally:
        try:
            publish("app_closed")
        except Exception as error:
            print(
                "Could not publish app_closed:",
                error,
            )

        if wake_engine is not None:
            try:
                wake_engine.close()
            except Exception as error:
                print(
                    "Wake engine shutdown error:",
                    error,
                )

        automation_runtime.stop()

        print("Baby shut down successfully.")


if __name__ == "__main__":
    start_baby()