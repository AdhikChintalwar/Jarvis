from __future__ import annotations

import asyncio
import subprocess
from typing import Any

from core.automation.outputs.base_output import (
    BaseOutput,
    OutputContext,
    OutputResult,
)
from core.automation.outputs.template_renderer import TemplateRenderer


class NotificationOutput(BaseOutput):
    type = "notification"
    description = "Displays a macOS desktop notification."

    def validate_config(
        self,
        config: dict[str, Any],
    ) -> None:
        super().validate_config(config)

        title = config.get("title")

        if title is not None and not isinstance(title, str):
            raise TypeError(
                "Notification title must be a string."
            )

        template = config.get("message_template")

        if template is not None and not isinstance(template, str):
            raise TypeError(
                "Notification message_template must be a string."
            )

    async def deliver(
        self,
        config: dict[str, Any],
        context: OutputContext,
    ) -> OutputResult:
        self.validate_config(config)

        title_template = config.get(
            "title",
            "Baby",
        )

        message_template = config.get(
            "message_template",
        )

        if message_template is None:
            message_template = self._default_message(context)

        title = TemplateRenderer.render(
            title_template,
            context.action_state,
        )

        message = TemplateRenderer.render(
            message_template,
            context.action_state,
        )

        try:
            await asyncio.to_thread(
                self._send_notification,
                title,
                message,
            )

            return OutputResult.succeeded(
                output_type=self.type,
                data={
                    "title": title,
                    "message": message,
                },
                message=message,
            )

        except Exception as error:
            return OutputResult.failed(
                output_type=self.type,
                error=str(error),
                data={
                    "title": title,
                    "message": message,
                },
            )

    @staticmethod
    def _send_notification(
        title: str,
        message: str,
    ) -> None:
        escaped_title = NotificationOutput._escape_applescript(
            title
        )
        escaped_message = NotificationOutput._escape_applescript(
            message
        )

        script = (
            f'display notification "{escaped_message}" '
            f'with title "{escaped_title}"'
        )

        completed = subprocess.run(
            [
                "osascript",
                "-e",
                script,
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )

        if completed.returncode != 0:
            error_message = completed.stderr.strip()

            raise RuntimeError(
                error_message
                or "Unable to display macOS notification."
            )

    @staticmethod
    def _escape_applescript(value: str) -> str:
        return (
            value.replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("\n", " ")
        )

    @staticmethod
    def _default_message(
        context: OutputContext,
    ) -> str:
        last_result = context.action_state.get("last_result")

        if isinstance(last_result, dict):
            message = last_result.get("message")

            if message:
                return str(message)

        if last_result is not None:
            return str(last_result)

        return f"Automation completed: {context.automation.name}"