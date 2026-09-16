from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from core.automation.outputs.base_output import (
    BaseOutput,
    OutputContext,
    OutputResult,
)
from core.automation.outputs.template_renderer import TemplateRenderer


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT_DIRECTORY = PROJECT_ROOT / "data" / "automation_outputs"


class SaveFileOutput(BaseOutput):
    type = "save_file"
    description = "Saves an automation result to a local file."

    def validate_config(
        self,
        config: dict[str, Any],
    ) -> None:
        super().validate_config(config)

        path = config.get("path")

        if not isinstance(path, str) or not path.strip():
            raise ValueError(
                "save_file output requires a non-empty 'path'."
            )

        mode = config.get("mode", "append")

        if mode not in {"append", "overwrite"}:
            raise ValueError(
                "save_file mode must be 'append' or 'overwrite'."
            )

        format_name = config.get("format", "text")

        if format_name not in {"text", "json"}:
            raise ValueError(
                "save_file format must be 'text' or 'json'."
            )

    async def deliver(
        self,
        config: dict[str, Any],
        context: OutputContext,
    ) -> OutputResult:
        self.validate_config(config)

        output_path = self._resolve_path(config["path"])
        mode = config.get("mode", "append")
        format_name = config.get("format", "text")

        if format_name == "json":
            content = json.dumps(
                {
                    "automation_id": context.automation.id,
                    "automation_name": context.automation.name,
                    "state": context.action_state,
                },
                ensure_ascii=False,
                indent=2,
                default=str,
            )
        else:
            template = config.get(
                "content_template",
                "{last_result}",
            )

            if not isinstance(template, str):
                raise TypeError(
                    "content_template must be a string."
                )

            content = TemplateRenderer.render(
                template,
                context.action_state,
            )

        await asyncio.to_thread(
            self._write_file,
            output_path,
            content,
            mode,
        )

        return OutputResult.succeeded(
            output_type=self.type,
            data={
                "path": str(output_path),
                "mode": mode,
                "format": format_name,
            },
            message=f"Saved automation output to {output_path}",
        )

    @staticmethod
    def _resolve_path(path_value: str) -> Path:
        path = Path(path_value).expanduser()

        if not path.is_absolute():
            path = DEFAULT_OUTPUT_DIRECTORY / path

        return path.resolve()

    @staticmethod
    def _write_file(
        path: Path,
        content: str,
        mode: str,
    ) -> None:
        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        file_mode = "a" if mode == "append" else "w"

        with path.open(
            file_mode,
            encoding="utf-8",
        ) as file:
            file.write(content)

            if not content.endswith("\n"):
                file.write("\n")