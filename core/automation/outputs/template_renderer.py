from __future__ import annotations

import re
from typing import Any


_TEMPLATE_PATTERN = re.compile(r"\{([^{}]+)\}")


class TemplateRenderer:
    """
    Renders values from nested dictionaries using dot notation.

    Example:

        "Battery is {last_result.percentage}%"
    """

    @classmethod
    def render(
        cls,
        template: str,
        data: dict[str, Any],
    ) -> str:
        if not isinstance(template, str):
            raise TypeError("Template must be a string.")

        if not isinstance(data, dict):
            raise TypeError("Template data must be a dictionary.")

        def replace(match: re.Match[str]) -> str:
            field_path = match.group(1).strip()

            try:
                value = cls.resolve(data, field_path)
            except (KeyError, TypeError, ValueError):
                return match.group(0)

            return str(value)

        return _TEMPLATE_PATTERN.sub(replace, template)

    @staticmethod
    def resolve(
        data: dict[str, Any],
        field_path: str,
    ) -> Any:
        current: Any = data

        for segment in field_path.split("."):
            segment = segment.strip()

            if not segment:
                raise ValueError(
                    f"Invalid template field: {field_path}"
                )

            if isinstance(current, dict):
                if segment not in current:
                    raise KeyError(field_path)

                current = current[segment]
                continue

            if isinstance(current, (list, tuple)):
                try:
                    index = int(segment)
                except ValueError as error:
                    raise KeyError(field_path) from error

                current = current[index]
                continue

            if hasattr(current, segment):
                current = getattr(current, segment)
                continue

            raise KeyError(field_path)

        return current