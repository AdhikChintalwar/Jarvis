from core.automation.outputs.base_output import (
    BaseOutput,
    OutputContext,
    OutputResult,
)
from core.automation.outputs.console_output import ConsoleOutput
from core.automation.outputs.notification_output import (
    NotificationOutput,
)
from core.automation.outputs.output_registry import (
    OutputRegistry,
    output_registry,
)
from core.automation.outputs.save_file_output import SaveFileOutput
from core.automation.outputs.template_renderer import TemplateRenderer


def register_builtin_outputs() -> None:
    """
    Register Baby's built-in outputs.

    Safe to call multiple times.
    """
    builtin_outputs = [
        ConsoleOutput(),
        NotificationOutput(),
        SaveFileOutput(),
    ]

    for output in builtin_outputs:
        if not output_registry.exists(output.type):
            output_registry.register(output)


__all__ = [
    "BaseOutput",
    "ConsoleOutput",
    "NotificationOutput",
    "OutputContext",
    "OutputRegistry",
    "OutputResult",
    "SaveFileOutput",
    "TemplateRenderer",
    "output_registry",
    "register_builtin_outputs",
]