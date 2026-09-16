from core.automation.actions.action_registry import (
    ActionRegistry,
    action_registry,
)
from core.automation.actions.base_action import (
    ActionContext,
    ActionResult,
    BaseAction,
)
from core.automation.actions.reminder_action import ReminderAction


def register_builtin_actions() -> None:
    """
    Register Baby's built-in automation actions.

    Safe to call more than once.
    """
    if not action_registry.exists(ReminderAction.name):
        action_registry.register(ReminderAction())


__all__ = [
    "ActionContext",
    "ActionRegistry",
    "ActionResult",
    "BaseAction",
    "ReminderAction",
    "action_registry",
    "register_builtin_actions",
]