from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.automation.models import ConditionDefinition


@dataclass
class ConditionEvaluation:
    """Result from evaluating one condition."""

    passed: bool
    field: str
    operator: str

    actual_value: Any = None
    expected_value: Any = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "field": self.field,
            "operator": self.operator,
            "actual_value": self.actual_value,
            "expected_value": self.expected_value,
            "error": self.error,
        }


@dataclass
class ConditionPipelineResult:
    """Complete result from evaluating all conditions."""

    passed: bool
    evaluations: list[ConditionEvaluation] = field(
        default_factory=list
    )
    mode: str = "all"
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "mode": self.mode,
            "evaluations": [
                evaluation.to_dict()
                for evaluation in self.evaluations
            ],
            "error": self.error,
        }


class ConditionEngine:
    """Evaluates generic automation conditions."""

    SUPPORTED_OPERATORS = {
        "equals",
        "not_equals",
        "greater_than",
        "greater_than_or_equal",
        "less_than",
        "less_than_or_equal",
        "contains",
        "not_contains",
        "starts_with",
        "ends_with",
        "in",
        "not_in",
        "exists",
        "not_exists",
        "is_empty",
        "is_not_empty",
        "is_true",
        "is_false",
    }

    OPERATOR_ALIASES = {
        "eq": "equals",
        "==": "equals",
        "ne": "not_equals",
        "!=": "not_equals",
        "gt": "greater_than",
        ">": "greater_than",
        "gte": "greater_than_or_equal",
        ">=": "greater_than_or_equal",
        "lt": "less_than",
        "<": "less_than",
        "lte": "less_than_or_equal",
        "<=": "less_than_or_equal",
    }

    def evaluate_all(
        self,
        conditions: list[ConditionDefinition],
        data: dict[str, Any],
        *,
        mode: str = "all",
    ) -> ConditionPipelineResult:
        """
        Evaluate all enabled conditions.

        mode="all": every condition must pass.
        mode="any": at least one condition must pass.
        """
        normalized_mode = mode.strip().lower()

        if normalized_mode not in {"all", "any"}:
            raise ValueError(
                "Condition mode must be either 'all' or 'any'."
            )

        if not isinstance(data, dict):
            raise TypeError(
                "Condition data must be a dictionary."
            )

        enabled_conditions = [
            condition
            for condition in conditions
            if condition.enabled
        ]

        if not enabled_conditions:
            return ConditionPipelineResult(
                passed=True,
                evaluations=[],
                mode=normalized_mode,
            )

        evaluations = [
            self.evaluate(condition, data)
            for condition in enabled_conditions
        ]

        if normalized_mode == "all":
            passed = all(
                evaluation.passed
                for evaluation in evaluations
            )
        else:
            passed = any(
                evaluation.passed
                for evaluation in evaluations
            )

        return ConditionPipelineResult(
            passed=passed,
            evaluations=evaluations,
            mode=normalized_mode,
        )

    def evaluate(
        self,
        condition: ConditionDefinition,
        data: dict[str, Any],
    ) -> ConditionEvaluation:
        """Evaluate one condition against the supplied data."""

        condition.validate()

        operator = self._normalize_operator(
            condition.operator
        )

        actual_value: Any = None

        try:
            try:
                actual_value = self._resolve_field(
                    data,
                    condition.field,
                )

            except KeyError:
                if operator == "not_exists":
                    actual_value = None

                elif operator == "exists":
                    return ConditionEvaluation(
                        passed=False,
                        field=condition.field,
                        operator=operator,
                        actual_value=None,
                        expected_value=condition.value,
                    )

                else:
                    raise

            passed = self._apply_operator(
                operator=operator,
                actual_value=actual_value,
                expected_value=condition.value,
            )

            return ConditionEvaluation(
                passed=passed,
                field=condition.field,
                operator=operator,
                actual_value=actual_value,
                expected_value=condition.value,
            )

        except Exception as error:
            return ConditionEvaluation(
                passed=False,
                field=condition.field,
                operator=operator,
                actual_value=actual_value,
                expected_value=condition.value,
                error=str(error),
            )

    def _normalize_operator(
        self,
        operator: str,
    ) -> str:
        if not isinstance(operator, str):
            raise TypeError(
                "Condition operator must be a string."
            )

        cleaned_operator = operator.strip().lower()

        cleaned_operator = self.OPERATOR_ALIASES.get(
            cleaned_operator,
            cleaned_operator,
        )

        if cleaned_operator not in self.SUPPORTED_OPERATORS:
            raise ValueError(
                f"Unsupported condition operator: {operator}"
            )

        return cleaned_operator

    def _resolve_field(
        self,
        data: dict[str, Any],
        field_path: str,
    ) -> Any:
        """Resolve nested values through dot notation."""

        if not isinstance(field_path, str):
            raise TypeError(
                "Condition field path must be a string."
            )

        cleaned_path = field_path.strip()

        if not cleaned_path:
            raise ValueError(
                "Condition field path cannot be empty."
            )

        current_value: Any = data

        for segment in cleaned_path.split("."):
            segment = segment.strip()

            if not segment:
                raise ValueError(
                    f"Invalid field path: {field_path}"
                )

            if isinstance(current_value, dict):
                if segment not in current_value:
                    raise KeyError(
                        f"Field does not exist: {field_path}"
                    )

                current_value = current_value[segment]
                continue

            if isinstance(current_value, (list, tuple)):
                try:
                    index = int(segment)
                except ValueError as error:
                    raise KeyError(
                        f"List field requires a numeric index: "
                        f"{field_path}"
                    ) from error

                try:
                    current_value = current_value[index]
                except IndexError as error:
                    raise KeyError(
                        f"List index is out of range: "
                        f"{field_path}"
                    ) from error

                continue

            if hasattr(current_value, segment):
                current_value = getattr(
                    current_value,
                    segment,
                )
                continue

            raise KeyError(
                f"Cannot resolve field: {field_path}"
            )

        return current_value

    def _apply_operator(
        self,
        *,
        operator: str,
        actual_value: Any,
        expected_value: Any,
    ) -> bool:
        if operator == "equals":
            return actual_value == expected_value

        if operator == "not_equals":
            return actual_value != expected_value

        if operator == "greater_than":
            return actual_value > expected_value

        if operator == "greater_than_or_equal":
            return actual_value >= expected_value

        if operator == "less_than":
            return actual_value < expected_value

        if operator == "less_than_or_equal":
            return actual_value <= expected_value

        if operator == "contains":
            return expected_value in actual_value

        if operator == "not_contains":
            return expected_value not in actual_value

        if operator == "starts_with":
            if not isinstance(actual_value, str):
                raise TypeError(
                    "starts_with requires a string value."
                )

            return actual_value.startswith(
                str(expected_value)
            )

        if operator == "ends_with":
            if not isinstance(actual_value, str):
                raise TypeError(
                    "ends_with requires a string value."
                )

            return actual_value.endswith(
                str(expected_value)
            )

        if operator == "in":
            return actual_value in expected_value

        if operator == "not_in":
            return actual_value not in expected_value

        if operator == "exists":
            return actual_value is not None

        if operator == "not_exists":
            return actual_value is None

        if operator == "is_empty":
            return self._is_empty(actual_value)

        if operator == "is_not_empty":
            return not self._is_empty(actual_value)

        if operator == "is_true":
            return actual_value is True

        if operator == "is_false":
            return actual_value is False

        raise ValueError(
            f"Unsupported condition operator: {operator}"
        )

    @staticmethod
    def _is_empty(value: Any) -> bool:
        if value is None:
            return True

        if isinstance(
            value,
            (
                str,
                list,
                tuple,
                set,
                dict,
                bytes,
            ),
        ):
            return len(value) == 0

        return False