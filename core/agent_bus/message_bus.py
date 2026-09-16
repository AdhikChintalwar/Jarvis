from __future__ import annotations

import queue
import threading
from collections import defaultdict
from typing import Callable

from core.agent_bus.models import (
    AgentMessage,
)


MessageHandler = Callable[
    [AgentMessage],
    None,
]


class AgentMessageBus:
    """
    Lightweight local agent-to-agent message bus.
    """

    def __init__(self) -> None:
        self._queues: dict[
            str,
            queue.Queue[AgentMessage],
        ] = defaultdict(
            queue.Queue
        )

        self._handlers: dict[
            str,
            list[MessageHandler],
        ] = defaultdict(list)

        self._lock = threading.RLock()

    def register_handler(
        self,
        agent_name: str,
        handler: MessageHandler,
    ) -> None:
        normalized = agent_name.strip().lower()

        with self._lock:
            self._handlers[
                normalized
            ].append(handler)

    def send(
        self,
        message: AgentMessage,
    ) -> None:
        recipient = (
            message.recipient
            .strip()
            .lower()
        )

        self._queues[
            recipient
        ].put(message)

        with self._lock:
            handlers = list(
                self._handlers.get(
                    recipient,
                    [],
                )
            )

        for handler in handlers:
            handler(message)

    def receive(
        self,
        agent_name: str,
        *,
        timeout: float | None = None,
    ) -> AgentMessage | None:

        normalized = (
            agent_name
            .strip()
            .lower()
        )

        try:
            return self._queues[
                normalized
            ].get(
                timeout=timeout
            )
        except queue.Empty:
            return None

    def pending_count(
        self,
        agent_name: str,
    ) -> int:
        normalized = (
            agent_name
            .strip()
            .lower()
        )

        return self._queues[
            normalized
        ].qsize()


agent_bus = AgentMessageBus()