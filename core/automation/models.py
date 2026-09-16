from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


def utc_now() -> datetime:
    """Return the current timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


def ensure_datetime(
    value: datetime | str | None,
) -> datetime | None:
    """
    Convert datetime strings into timezone-aware datetime objects.

    Naive datetimes are interpreted as UTC.
    """
    if value is None:
        return None

    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)

        return value.astimezone(timezone.utc)

    if isinstance(value, str):
        cleaned = value.strip()

        if not cleaned:
            return None

        if cleaned.endswith("Z"):
            cleaned = cleaned[:-1] + "+00:00"

        try:
            parsed = datetime.fromisoformat(cleaned)
        except ValueError as error:
            raise ValueError(
                f"Invalid ISO datetime value: {value}"
            ) from error

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)

        return parsed.astimezone(timezone.utc)

    raise TypeError(
        "Datetime value must be a datetime, ISO string, or None."
    )


def datetime_to_iso(
    value: datetime | str | None,
) -> str | None:
    """Convert a datetime-like value into an ISO string."""
    parsed = ensure_datetime(value)

    if parsed is None:
        return None

    return parsed.isoformat()


class TriggerType(str, Enum):
    """Supported automation trigger types."""

    ONCE = "once"
    DATE = "date"
    INTERVAL = "interval"
    DAILY = "daily"
    CRON = "cron"
    STARTUP = "startup"
    MANUAL = "manual"
    EVENT = "event"


class AutomationStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    DISABLED = "disabled"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class TriggerDefinition:
    """Defines when an automation should run."""

    type: TriggerType
    config: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if not isinstance(self.type, TriggerType):
            try:
                self.type = TriggerType(
                    str(self.type).strip().lower()
                )
            except ValueError as error:
                raise ValueError(
                    f"Unsupported trigger type: {self.type}"
                ) from error

        if not isinstance(self.config, dict):
            raise TypeError(
                "Trigger config must be a dictionary."
            )

        if self.type in {
            TriggerType.ONCE,
            TriggerType.DATE,
        }:
            run_at = (
                self.config.get("run_at")
                or self.config.get("datetime")
                or self.config.get("date")
            )

            if not run_at:
                raise ValueError(
                    "A once/date trigger requires "
                    "config['run_at']."
                )

            ensure_datetime(run_at)

        elif self.type == TriggerType.INTERVAL:
            allowed_fields = {
                "seconds",
                "minutes",
                "hours",
                "days",
                "weeks",
            }

            supplied_values = [
                self.config[field_name]
                for field_name in allowed_fields
                if self.config.get(field_name) is not None
            ]

            if not supplied_values:
                raise ValueError(
                    "An interval trigger requires seconds, "
                    "minutes, hours, days, or weeks."
                )

            for value in supplied_values:
                if (
                    isinstance(value, bool)
                    or not isinstance(value, (int, float))
                    or value <= 0
                ):
                    raise ValueError(
                        "Interval values must be positive numbers."
                    )

        elif self.type == TriggerType.DAILY:
            run_time = self.config.get("time")

            if not isinstance(run_time, str) or not run_time.strip():
                raise ValueError(
                    "A daily trigger requires config['time']."
                )

        elif self.type == TriggerType.CRON:
            if not self.config:
                raise ValueError(
                    "A cron trigger requires at least one "
                    "schedule field."
                )

        elif self.type == TriggerType.EVENT:
            if not self.config.get("event_name"):
                raise ValueError(
                    "An event trigger requires "
                    "config['event_name']."
                )


@dataclass
class ActionDefinition:
    """Defines an automation action plugin invocation."""

    name: str
    arguments: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError(
                "Action name cannot be empty."
            )

        self.name = self.name.strip()

        if not isinstance(self.arguments, dict):
            raise TypeError(
                "Action arguments must be a dictionary."
            )


@dataclass
class ConditionDefinition:
    """Defines an optional automation condition."""

    field: str
    operator: str
    value: Any = None
    enabled: bool = True

    def validate(self) -> None:
        if not isinstance(self.field, str) or not self.field.strip():
            raise ValueError(
                "Condition field cannot be empty."
            )

        if (
            not isinstance(self.operator, str)
            or not self.operator.strip()
        ):
            raise ValueError(
                "Condition operator cannot be empty."
            )

        self.field = self.field.strip()
        self.operator = self.operator.strip().lower()
        self.enabled = bool(self.enabled)


@dataclass
class OutputDefinition:
    """Defines how automation results are delivered."""

    type: str
    config: dict[str, Any] = field(default_factory=dict)
    enabled: bool = True

    def validate(self) -> None:
        if not isinstance(self.type, str) or not self.type.strip():
            raise ValueError(
                "Output type cannot be empty."
            )

        self.type = self.type.strip()

        if not isinstance(self.config, dict):
            raise TypeError(
                "Output config must be a dictionary."
            )

        self.enabled = bool(self.enabled)


@dataclass
class Automation:
    """
    Generic automation definition used by the scheduler,
    executor, engines, and SQLite store.
    """

    name: str
    trigger: TriggerDefinition
    actions: list[ActionDefinition]

    conditions: list[ConditionDefinition] = field(
        default_factory=list
    )
    outputs: list[OutputDefinition] = field(
        default_factory=list
    )

    id: str = field(
        default_factory=lambda: (
            f"automation_{uuid4().hex[:12]}"
        )
    )

    description: str = ""
    status: AutomationStatus = AutomationStatus.ACTIVE
    enabled: bool = True

    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    last_run: datetime | None = None
    next_run: datetime | None = None

    last_error: str | None = None
    run_count: int = 0

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        """
        Normalize values supplied directly to the dataclass.

        This also supports old saved JSON where datetime values
        were represented as strings.
        """
        self.created_at = (
            ensure_datetime(self.created_at)
            or utc_now()
        )

        self.updated_at = (
            ensure_datetime(self.updated_at)
            or utc_now()
        )

        self.last_run = ensure_datetime(
            self.last_run
        )

        self.next_run = ensure_datetime(
            self.next_run
        )

    # ---------------------------------------------------------
    # Backward-compatible property aliases
    # ---------------------------------------------------------

    @property
    def last_run_at(self) -> datetime | None:
        return self.last_run

    @last_run_at.setter
    def last_run_at(
        self,
        value: datetime | str | None,
    ) -> None:
        self.last_run = ensure_datetime(value)

    @property
    def next_run_at(self) -> datetime | None:
        return self.next_run

    @next_run_at.setter
    def next_run_at(
        self,
        value: datetime | str | None,
    ) -> None:
        self.next_run = ensure_datetime(value)

    # ---------------------------------------------------------
    # Validation
    # ---------------------------------------------------------

    def validate(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError(
                "Automation name cannot be empty."
            )

        self.name = self.name.strip()

        if not isinstance(self.description, str):
            raise TypeError(
                "Automation description must be a string."
            )

        if not isinstance(self.trigger, TriggerDefinition):
            raise TypeError(
                "Automation trigger must be a "
                "TriggerDefinition."
            )

        self.trigger.validate()

        if not isinstance(self.actions, list) or not self.actions:
            raise ValueError(
                "An automation must contain at least one action."
            )

        for action in self.actions:
            if not isinstance(action, ActionDefinition):
                raise TypeError(
                    "Every action must be an ActionDefinition."
                )

            action.validate()

        if not isinstance(self.conditions, list):
            raise TypeError(
                "Automation conditions must be a list."
            )

        for condition in self.conditions:
            if not isinstance(
                condition,
                ConditionDefinition,
            ):
                raise TypeError(
                    "Every condition must be a "
                    "ConditionDefinition."
                )

            condition.validate()

        if not isinstance(self.outputs, list):
            raise TypeError(
                "Automation outputs must be a list."
            )

        for output in self.outputs:
            if not isinstance(output, OutputDefinition):
                raise TypeError(
                    "Every output must be an OutputDefinition."
                )

            output.validate()

        if not isinstance(self.status, AutomationStatus):
            try:
                self.status = AutomationStatus(
                    str(self.status).strip().lower()
                )
            except ValueError as error:
                raise ValueError(
                    f"Unsupported automation status: "
                    f"{self.status}"
                ) from error

        self.enabled = bool(self.enabled)

        if (
            isinstance(self.run_count, bool)
            or not isinstance(self.run_count, int)
        ):
            raise TypeError(
                "Automation run count must be an integer."
            )

        if self.run_count < 0:
            raise ValueError(
                "Automation run count cannot be negative."
            )

        if not isinstance(self.metadata, dict):
            raise TypeError(
                "Automation metadata must be a dictionary."
            )

        self.created_at = (
            ensure_datetime(self.created_at)
            or utc_now()
        )
        self.updated_at = (
            ensure_datetime(self.updated_at)
            or utc_now()
        )
        self.last_run = ensure_datetime(
            self.last_run
        )
        self.next_run = ensure_datetime(
            self.next_run
        )

    # ---------------------------------------------------------
    # Lifecycle helpers
    # ---------------------------------------------------------

    def touch(self) -> None:
        self.updated_at = utc_now()

    def mark_running_result(
        self,
        *,
        succeeded: bool,
        error: str | None = None,
    ) -> None:
        self.last_run = utc_now()
        self.run_count += 1
        self.last_error = error

        if succeeded:
            if self.status == AutomationStatus.FAILED:
                self.status = AutomationStatus.ACTIVE
        else:
            self.status = AutomationStatus.FAILED

        self.touch()

    def pause(self) -> None:
        self.status = AutomationStatus.PAUSED
        self.enabled = False
        self.next_run = None
        self.touch()

    def resume(self) -> None:
        self.status = AutomationStatus.ACTIVE
        self.enabled = True
        self.last_error = None
        self.touch()

    def disable(self) -> None:
        self.status = AutomationStatus.DISABLED
        self.enabled = False
        self.next_run = None
        self.touch()

    def complete(self) -> None:
        self.status = AutomationStatus.COMPLETED
        self.enabled = False
        self.next_run = None
        self.touch()

    # ---------------------------------------------------------
    # Serialization
    # ---------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """
        Convert the automation into a JSON-compatible dictionary.
        """
        self.validate()

        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "trigger": {
                "type": self.trigger.type.value,
                "config": dict(self.trigger.config),
            },
            "actions": [
                {
                    "name": action.name,
                    "arguments": dict(action.arguments),
                }
                for action in self.actions
            ],
            "conditions": [
                {
                    "field": condition.field,
                    "operator": condition.operator,
                    "value": condition.value,
                    "enabled": condition.enabled,
                }
                for condition in self.conditions
            ],
            "outputs": [
                {
                    "type": output.type,
                    "config": dict(output.config),
                    "enabled": output.enabled,
                }
                for output in self.outputs
            ],
            "status": self.status.value,
            "enabled": self.enabled,
            "created_at": datetime_to_iso(
                self.created_at
            ),
            "updated_at": datetime_to_iso(
                self.updated_at
            ),
            "last_run": datetime_to_iso(
                self.last_run
            ),
            "next_run": datetime_to_iso(
                self.next_run
            ),
            "last_error": self.last_error,
            "run_count": self.run_count,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
    ) -> "Automation":
        """
        Rebuild an Automation from JSON-compatible data.

        Older keys last_run_at and next_run_at are accepted.
        """
        if not isinstance(data, dict):
            raise TypeError(
                "Automation data must be a dictionary."
            )

        trigger_data = data.get("trigger")

        if not isinstance(trigger_data, dict):
            raise ValueError(
                "Automation data is missing a trigger."
            )

        if "type" not in trigger_data:
            raise ValueError(
                "Automation trigger is missing its type."
            )

        action_data = data.get("actions", [])
        condition_data = data.get("conditions", [])
        output_data = data.get("outputs", [])

        if not isinstance(action_data, list):
            raise TypeError(
                "Stored actions must be a list."
            )

        if not isinstance(condition_data, list):
            raise TypeError(
                "Stored conditions must be a list."
            )

        if not isinstance(output_data, list):
            raise TypeError(
                "Stored outputs must be a list."
            )

        last_run_value = data.get(
            "last_run",
            data.get("last_run_at"),
        )

        next_run_value = data.get(
            "next_run",
            data.get("next_run_at"),
        )

        automation = cls(
            id=data.get(
                "id",
                f"automation_{uuid4().hex[:12]}",
            ),
            name=data.get("name", ""),
            description=data.get(
                "description",
                "",
            ),
            trigger=TriggerDefinition(
                type=TriggerType(
                    trigger_data["type"]
                ),
                config=dict(
                    trigger_data.get(
                        "config",
                        {},
                    )
                ),
            ),
            actions=[
                ActionDefinition(
                    name=action["name"],
                    arguments=dict(
                        action.get(
                            "arguments",
                            {},
                        )
                    ),
                )
                for action in action_data
            ],
            conditions=[
                ConditionDefinition(
                    field=condition["field"],
                    operator=condition["operator"],
                    value=condition.get("value"),
                    enabled=condition.get(
                        "enabled",
                        True,
                    ),
                )
                for condition in condition_data
            ],
            outputs=[
                OutputDefinition(
                    type=output["type"],
                    config=dict(
                        output.get(
                            "config",
                            {},
                        )
                    ),
                    enabled=output.get(
                        "enabled",
                        True,
                    ),
                )
                for output in output_data
            ],
            status=AutomationStatus(
                data.get(
                    "status",
                    AutomationStatus.ACTIVE.value,
                )
            ),
            enabled=data.get("enabled", True),
            created_at=(
                ensure_datetime(
                    data.get("created_at")
                )
                or utc_now()
            ),
            updated_at=(
                ensure_datetime(
                    data.get("updated_at")
                )
                or utc_now()
            ),
            last_run=ensure_datetime(
                last_run_value
            ),
            next_run=ensure_datetime(
                next_run_value
            ),
            last_error=data.get("last_error"),
            run_count=int(
                data.get("run_count", 0)
            ),
            metadata=dict(
                data.get("metadata", {})
            ),
        )

        automation.validate()
        return automation