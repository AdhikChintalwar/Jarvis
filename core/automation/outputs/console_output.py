from __future__ import annotations

from typing import Any

from core.automation.outputs.base_output import (
    BaseOutput,
    OutputContext,
    OutputResult,
)
from core.automation.outputs.template_renderer import TemplateRenderer


class ConsoleOutput(BaseOutput):
    type = "console"
    description = "Prints an automation result to the terminal."

    async def deliver(
        self,
        config: dict[str, Any],
        context: OutputContext,
    ) -> OutputResult:
        self.validate_config(config)

        template = config.get("message_template")

        if template is None:
            template = self._default_message(context)

        if not isinstance(template, str):
            raise TypeError(
                "Console message_template must be a string."
            )

        rendered_message = TemplateRenderer.render(
            template,
            context.action_state,
        )

        print(rendered_message)

        return OutputResult.succeeded(
            output_type=self.type,
            data={
                "rendered_message": rendered_message,
            },
            message=rendered_message,
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