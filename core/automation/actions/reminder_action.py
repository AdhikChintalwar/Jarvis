from __future__ import annotations

from typing import Any

from core.automation.actions.base_action import (
    ActionContext,
    ActionResult,
    BaseAction,
)


class ReminderAction(BaseAction):
    name = "reminder"
    description = "Creates a reminder message for an automation output."

    def validate_arguments(
        self,
        arguments: dict[str, Any],
    ) -> None:
        super().validate_arguments(arguments)

        message = arguments.get("message")

        if not isinstance(message, str) or not message.strip():
            raise ValueError(
                "Reminder action requires a non-empty 'message'."
            )

        title = arguments.get("title")

        if title is not None and not isinstance(title, str):
            raise TypeError(
                "Reminder title must be a string."
            )

    async def execute(
        self,
        arguments: dict[str, Any],
        context: ActionContext,
    ) -> ActionResult:
        self.validate_arguments(arguments)

        message = arguments["message"].strip()
        title = arguments.get("title", "Baby Reminder")

        if isinstance(title, str):
            title = title.strip() or "Baby Reminder"

        reminder_data = {
            "title": title,
            "message": message,
            "automation_id": context.automation.id,
            "automation_name": context.automation.name,
        }

        return ActionResult.succeeded(
            data=reminder_data,
            message=message,
        )