from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from core.automation.models import Automation


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class TriggerEvaluation:
    """
    Result of calculating an automation trigger.
    """

    supported: bool
    trigger_type: str
    next_run: datetime | None
    should_run_now: bool = False
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "supported": self.supported,
            "trigger_type": self.trigger_type,
            "next_run": (
                self.next_run.isoformat()
                if self.next_run is not None
                else None
            ),
            "should_run_now": self.should_run_now,
            "error": self.error,
        }


class TriggerEngine:
    """
    Interprets automation trigger definitions.

    Supported trigger types:

    manual
        Never scheduled automatically.

    interval
        Runs repeatedly after a configured duration.

        Config examples:

            {"seconds": 30}
            {"minutes": 5}
            {"hours": 2}
            {"days": 1}

    once / date
        Runs once at an ISO-formatted datetime.

        Config example:

            {"run_at": "2026-07-29T10:30:00-04:00"}

    daily
        Runs every day at a local clock time.

        Config example:

            {
                "time": "09:00",
                "timezone": "America/New_York"
            }
    """

    SUPPORTED_TYPES = {
        "manual",
        "interval",
        "once",
        "date",
        "daily",
    }

    def get_trigger_type(
        self,
        automation: Automation,
    ) -> str:
        trigger = automation.trigger
        raw_type = getattr(trigger, "type", None)

        if raw_type is None:
            raise ValueError(
                "Automation trigger does not define a type."
            )

        enum_value = getattr(raw_type, "value", raw_type)

        if not isinstance(enum_value, str):
            raise TypeError(
                "Trigger type must be a string or enum."
            )

        normalized = enum_value.strip().lower()

        if not normalized:
            raise ValueError(
                "Trigger type cannot be empty."
            )

        return normalized

    def get_trigger_config(
        self,
        automation: Automation,
    ) -> dict[str, Any]:
        config = getattr(
            automation.trigger,
            "config",
            {},
        )

        if config is None:
            return {}

        if not isinstance(config, dict):
            raise TypeError(
                "Trigger config must be a dictionary."
            )

        return dict(config)

    def calculate_next_run(
        self,
        automation: Automation,
        *,
        from_time: datetime | None = None,
    ) -> TriggerEvaluation:
        """
        Calculate the next scheduled execution time.
        """
        reference_time = self._ensure_aware(
            from_time or utc_now()
        )

        try:
            trigger_type = self.get_trigger_type(
                automation
            )
            config = self.get_trigger_config(
                automation
            )

            if trigger_type not in self.SUPPORTED_TYPES:
                return TriggerEvaluation(
                    supported=False,
                    trigger_type=trigger_type,
                    next_run=None,
                    error=(
                        f"Unsupported trigger type: "
                        f"{trigger_type}"
                    ),
                )

            if trigger_type == "manual":
                return TriggerEvaluation(
                    supported=True,
                    trigger_type=trigger_type,
                    next_run=None,
                )

            if trigger_type == "interval":
                next_run = self._calculate_interval(
                    config,
                    reference_time,
                )

            elif trigger_type in {"once", "date"}:
                next_run = self._calculate_once(
                    config
                )

            elif trigger_type == "daily":
                next_run = self._calculate_daily(
                    config,
                    reference_time,
                )

            else:
                raise ValueError(
                    f"Unsupported trigger type: "
                    f"{trigger_type}"
                )

            should_run_now = (
                next_run is not None
                and next_run <= reference_time
            )

            return TriggerEvaluation(
                supported=True,
                trigger_type=trigger_type,
                next_run=next_run,
                should_run_now=should_run_now,
            )

        except Exception as error:
            trigger_type = "unknown"

            try:
                trigger_type = self.get_trigger_type(
                    automation
                )
            except Exception:
                pass

            return TriggerEvaluation(
                supported=False,
                trigger_type=trigger_type,
                next_run=None,
                error=str(error),
            )

    def calculate_after_execution(
        self,
        automation: Automation,
        *,
        executed_at: datetime | None = None,
    ) -> datetime | None:
        """
        Calculate the next run after an execution finishes.
        """
        trigger_type = self.get_trigger_type(
            automation
        )

        if trigger_type in {
            "manual",
            "once",
            "date",
        }:
            return None

        evaluation = self.calculate_next_run(
            automation,
            from_time=executed_at or utc_now(),
        )

        if not evaluation.supported:
            raise ValueError(
                evaluation.error
                or "Unable to calculate next run."
            )

        return evaluation.next_run

    def is_due(
        self,
        automation: Automation,
        *,
        now: datetime | None = None,
    ) -> bool:
        """
        Return True if the automation's stored next_run is due.
        """
        current_time = self._ensure_aware(
            now or utc_now()
        )

        next_run = getattr(
            automation,
            "next_run",
            None,
        )

        if next_run is None:
            return False

        return (
            self._ensure_aware(next_run)
            <= current_time
        )

    def _calculate_interval(
        self,
        config: dict[str, Any],
        reference_time: datetime,
    ) -> datetime:
        seconds = self._interval_seconds(config)

        if seconds <= 0:
            raise ValueError(
                "Interval duration must be greater than zero."
            )

        return reference_time + timedelta(
            seconds=seconds
        )

    @staticmethod
    def _interval_seconds(
        config: dict[str, Any],
    ) -> float:
        units = {
            "seconds": 1,
            "minutes": 60,
            "hours": 3600,
            "days": 86400,
        }

        total = 0.0
        found = False

        for key, multiplier in units.items():
            if key not in config:
                continue

            found = True
            value = config[key]

            if isinstance(value, bool):
                raise TypeError(
                    f"{key} must be numeric."
                )

            try:
                numeric_value = float(value)
            except (TypeError, ValueError) as error:
                raise TypeError(
                    f"{key} must be numeric."
                ) from error

            if numeric_value < 0:
                raise ValueError(
                    f"{key} cannot be negative."
                )

            total += numeric_value * multiplier

        if not found:
            raise ValueError(
                "Interval trigger requires seconds, minutes, "
                "hours, or days."
            )

        return total

    def _calculate_once(
        self,
        config: dict[str, Any],
    ) -> datetime:
        raw_value = (
            config.get("run_at")
            or config.get("datetime")
            or config.get("date")
        )

        if raw_value is None:
            raise ValueError(
                "Once trigger requires 'run_at'."
            )

        return self._parse_datetime(
            raw_value,
            config.get("timezone"),
        )

    def _calculate_daily(
        self,
        config: dict[str, Any],
        reference_time: datetime,
    ) -> datetime:
        raw_time = config.get("time")

        if not isinstance(raw_time, str):
            raise ValueError(
                "Daily trigger requires a time such as '09:30'."
            )

        timezone_name = config.get(
            "timezone",
            "UTC",
        )

        if not isinstance(timezone_name, str):
            raise TypeError(
                "Daily trigger timezone must be a string."
            )

        try:
            local_timezone = ZoneInfo(
                timezone_name
            )
        except Exception as error:
            raise ValueError(
                f"Invalid timezone: {timezone_name}"
            ) from error

        parsed_time = self._parse_clock_time(
            raw_time
        )

        local_reference = reference_time.astimezone(
            local_timezone
        )

        local_candidate = datetime.combine(
            local_reference.date(),
            parsed_time,
            tzinfo=local_timezone,
        )

        if local_candidate <= local_reference:
            local_candidate += timedelta(days=1)

        return local_candidate.astimezone(
            timezone.utc
        )

    @staticmethod
    def _parse_clock_time(
        raw_time: str,
    ) -> time:
        cleaned = raw_time.strip()

        formats = [
            "%H:%M:%S",
            "%H:%M",
        ]

        for format_string in formats:
            try:
                return datetime.strptime(
                    cleaned,
                    format_string,
                ).time()
            except ValueError:
                continue

        raise ValueError(
            "Time must use HH:MM or HH:MM:SS."
        )

    def _parse_datetime(
        self,
        value: Any,
        timezone_name: Any = None,
    ) -> datetime:
        if isinstance(value, datetime):
            parsed = value
        elif isinstance(value, str):
            cleaned = value.strip()

            if cleaned.endswith("Z"):
                cleaned = (
                    cleaned[:-1] + "+00:00"
                )

            try:
                parsed = datetime.fromisoformat(
                    cleaned
                )
            except ValueError as error:
                raise ValueError(
                    "run_at must be an ISO-formatted datetime."
                ) from error
        else:
            raise TypeError(
                "run_at must be a datetime or string."
            )

        if parsed.tzinfo is None:
            if timezone_name is None:
                parsed = parsed.replace(
                    tzinfo=timezone.utc
                )
            else:
                try:
                    parsed = parsed.replace(
                        tzinfo=ZoneInfo(
                            str(timezone_name)
                        )
                    )
                except Exception as error:
                    raise ValueError(
                        f"Invalid timezone: {timezone_name}"
                    ) from error

        return parsed.astimezone(timezone.utc)

    @staticmethod
    def _ensure_aware(
        value: datetime,
    ) -> datetime:
        if not isinstance(value, datetime):
            raise TypeError(
                "Expected a datetime value."
            )

        if value.tzinfo is None:
            return value.replace(
                tzinfo=timezone.utc
            )

        return value.astimezone(timezone.utc)