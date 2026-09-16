from __future__ import annotations

import threading
from typing import TypeVar

from core.automation.outputs.base_output import BaseOutput


OutputType = TypeVar("OutputType", bound=BaseOutput)


class OutputRegistry:
    """
    Stores all output plugins available to Baby.
    """

    def __init__(self) -> None:
        self._outputs: dict[str, BaseOutput] = {}
        self._lock = threading.RLock()

    @staticmethod
    def _normalize_type(output_type: str) -> str:
        if not isinstance(output_type, str) or not output_type.strip():
            raise ValueError("Output type cannot be empty.")

        return output_type.strip().lower()

    def register(
        self,
        output: BaseOutput,
        *,
        replace: bool = False,
    ) -> BaseOutput:
        if not isinstance(output, BaseOutput):
            raise TypeError(
                "Registered output must inherit from BaseOutput."
            )

        output_type = self._normalize_type(output.type)

        with self._lock:
            if output_type in self._outputs and not replace:
                raise ValueError(
                    f"Output is already registered: {output_type}"
                )

            self._outputs[output_type] = output

        return output

    def register_class(
        self,
        output_class: type[OutputType],
        *,
        replace: bool = False,
    ) -> OutputType:
        output = output_class()
        self.register(output, replace=replace)
        return output

    def unregister(self, output_type: str) -> bool:
        normalized = self._normalize_type(output_type)

        with self._lock:
            return self._outputs.pop(normalized, None) is not None

    def get(self, output_type: str) -> BaseOutput | None:
        normalized = self._normalize_type(output_type)

        with self._lock:
            return self._outputs.get(normalized)

    def get_required(self, output_type: str) -> BaseOutput:
        output = self.get(output_type)

        if output is None:
            raise KeyError(
                f"Unknown automation output: {output_type}"
            )

        return output

    def exists(self, output_type: str) -> bool:
        normalized = self._normalize_type(output_type)

        with self._lock:
            return normalized in self._outputs

    def list_types(self) -> list[str]:
        with self._lock:
            return sorted(self._outputs.keys())

    def list_outputs(self) -> list[dict[str, str]]:
        with self._lock:
            return [
                {
                    "type": output.type,
                    "description": output.description,
                }
                for output in sorted(
                    self._outputs.values(),
                    key=lambda item: item.type,
                )
            ]

    def clear(self) -> None:
        with self._lock:
            self._outputs.clear()


output_registry = OutputRegistry()