from __future__ import annotations

import threading
from typing import TypeVar

from core.automation.actions.base_action import BaseAction


ActionType = TypeVar("ActionType", bound=BaseAction)


class ActionRegistry:
    """
    Stores all action plugins available to Baby.

    The automation engine requests actions by name without importing
    individual action implementations.
    """

    def __init__(self) -> None:
        self._actions: dict[str, BaseAction] = {}
        self._lock = threading.RLock()

    @staticmethod
    def _normalize_name(name: str) -> str:
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Action name cannot be empty.")

        return name.strip().lower()

    def register(
        self,
        action: BaseAction,
        *,
        replace: bool = False,
    ) -> BaseAction:
        """
        Register an instantiated action plugin.
        """
        if not isinstance(action, BaseAction):
            raise TypeError(
                "Registered action must inherit from BaseAction."
            )

        action_name = self._normalize_name(action.name)

        with self._lock:
            if action_name in self._actions and not replace:
                raise ValueError(
                    f"Action is already registered: {action_name}"
                )

            self._actions[action_name] = action

        return action

    def register_class(
        self,
        action_class: type[ActionType],
        *,
        replace: bool = False,
    ) -> ActionType:
        """
        Instantiate and register an action class.
        """
        action = action_class()
        self.register(action, replace=replace)
        return action

    def unregister(self, name: str) -> bool:
        action_name = self._normalize_name(name)

        with self._lock:
            return self._actions.pop(action_name, None) is not None

    def get(self, name: str) -> BaseAction | None:
        action_name = self._normalize_name(name)

        with self._lock:
            return self._actions.get(action_name)

    def get_required(self, name: str) -> BaseAction:
        action = self.get(name)

        if action is None:
            raise KeyError(
                f"Unknown automation action: {name}"
            )

        return action

    def exists(self, name: str) -> bool:
        action_name = self._normalize_name(name)

        with self._lock:
            return action_name in self._actions

    def list_names(self) -> list[str]:
        with self._lock:
            return sorted(self._actions.keys())

    def list_actions(self) -> list[dict[str, str]]:
        with self._lock:
            return [
                {
                    "name": action.name,
                    "description": action.description,
                }
                for action in sorted(
                    self._actions.values(),
                    key=lambda item: item.name,
                )
            ]

    def clear(self) -> None:
        with self._lock:
            self._actions.clear()


action_registry = ActionRegistry()