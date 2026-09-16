from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.automation.models import (
    Automation,
    AutomationStatus,
)


def utc_now() -> datetime:
    """Return the current timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    """Return the current UTC datetime as an ISO-formatted string."""
    return utc_now().isoformat()


def datetime_to_iso(
    value: datetime | str | None,
) -> str | None:
    """Convert a datetime or ISO string to an ISO string."""
    if value is None:
        return None

    if isinstance(value, str):
        cleaned = value.strip()

        if not cleaned:
            return None

        if cleaned.endswith("Z"):
            cleaned = cleaned[:-1] + "+00:00"

        try:
            value = datetime.fromisoformat(cleaned)
        except ValueError as error:
            raise ValueError(
                f"Invalid ISO datetime: {value}"
            ) from error

    if not isinstance(value, datetime):
        raise TypeError(
            "Expected datetime, ISO string, or None."
        )

    if value.tzinfo is None:
        value = value.replace(
            tzinfo=timezone.utc
        )

    return value.astimezone(
        timezone.utc
    ).isoformat()


def parse_json_object(
    value: str | None,
) -> dict[str, Any]:
    """Safely parse a JSON object stored in SQLite."""
    if not value:
        return {}

    try:
        parsed = json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return {}

    return parsed if isinstance(parsed, dict) else {}


class AutomationStore:
    """
    SQLite persistence layer for Baby automations.

    Responsibilities:

    - Save and load automation definitions
    - List and search automations
    - Update scheduling information
    - Record execution history
    - Update execution statistics

    This class does not execute or schedule automations.
    """

    def __init__(
        self,
        database_path: str | Path = "data/baby_automations.db",
    ) -> None:
        self.database_path = Path(
            database_path
        ).expanduser().resolve()

        self.database_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._lock = threading.RLock()
        self._closed = False

        self._connection = sqlite3.connect(
            str(self.database_path),
            check_same_thread=False,
            timeout=30,
        )

        self._connection.row_factory = sqlite3.Row

        with self._lock:
            self._connection.execute(
                "PRAGMA foreign_keys = ON"
            )
            self._connection.execute(
                "PRAGMA journal_mode = WAL"
            )
            self._connection.execute(
                "PRAGMA synchronous = NORMAL"
            )
            self._connection.execute(
                "PRAGMA busy_timeout = 30000"
            )

        self._initialize_database()

    # ---------------------------------------------------------
    # Database initialization
    # ---------------------------------------------------------

    def _initialize_database(self) -> None:
        """Create all required tables and indexes."""
        with self._lock:
            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS automations (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',

                    enabled INTEGER NOT NULL DEFAULT 1,
                    status TEXT NOT NULL DEFAULT 'active',

                    automation_json TEXT NOT NULL,

                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,

                    last_run TEXT,
                    next_run TEXT,

                    run_count INTEGER NOT NULL DEFAULT 0
                )
                """
            )

            self._connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_automations_name
                ON automations(name)
                """
            )

            self._connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_automations_enabled
                ON automations(enabled)
                """
            )

            self._connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_automations_status
                ON automations(status)
                """
            )

            self._connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_automations_next_run
                ON automations(next_run)
                """
            )

            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS automation_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    automation_id TEXT NOT NULL,

                    status TEXT NOT NULL,
                    trigger_source TEXT,

                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    stopped_at_phase TEXT,

                    runtime_data_json TEXT NOT NULL DEFAULT '{}',
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    result_json TEXT NOT NULL DEFAULT '{}',

                    error TEXT,

                    FOREIGN KEY (automation_id)
                        REFERENCES automations(id)
                        ON DELETE CASCADE
                )
                """
            )

            self._connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_automation_runs_automation_id
                ON automation_runs(automation_id)
                """
            )

            self._connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_automation_runs_status
                ON automation_runs(status)
                """
            )

            self._connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_automation_runs_started_at
                ON automation_runs(started_at)
                """
            )

            self._connection.commit()

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError(
                "AutomationStore has already been closed."
            )

    # ---------------------------------------------------------
    # Automation CRUD
    # ---------------------------------------------------------

    def save(
        self,
        automation: Automation,
    ) -> Automation:
        """
        Insert or update an automation.

        The full automation is stored as JSON while frequently queried
        fields are also stored in dedicated columns.
        """
        self._ensure_open()

        if not isinstance(automation, Automation):
            raise TypeError(
                "automation must be an Automation instance."
            )

        automation.validate()

        now = utc_now()

        if getattr(automation, "created_at", None) is None:
            automation.created_at = now

        automation.updated_at = now

        automation_json = json.dumps(
            automation.to_dict(),
            ensure_ascii=False,
            default=str,
        )

        status_value = self._status_value(
            automation.status
        )

        with self._lock:
            self._connection.execute(
                """
                INSERT INTO automations (
                    id,
                    name,
                    description,
                    enabled,
                    status,
                    automation_json,
                    created_at,
                    updated_at,
                    last_run,
                    next_run,
                    run_count
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)

                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    description = excluded.description,
                    enabled = excluded.enabled,
                    status = excluded.status,
                    automation_json = excluded.automation_json,
                    updated_at = excluded.updated_at,
                    last_run = excluded.last_run,
                    next_run = excluded.next_run,
                    run_count = excluded.run_count
                """,
                (
                    automation.id,
                    automation.name,
                    automation.description or "",
                    1 if automation.enabled else 0,
                    status_value,
                    automation_json,
                    datetime_to_iso(automation.created_at)
                    or utc_now_iso(),
                    datetime_to_iso(automation.updated_at)
                    or utc_now_iso(),
                    datetime_to_iso(automation.last_run),
                    datetime_to_iso(automation.next_run),
                    int(automation.run_count or 0),
                ),
            )

            self._connection.commit()

        return automation

    def get(
        self,
        automation_id: str,
    ) -> Automation | None:
        """Return an automation or None when it does not exist."""
        self._ensure_open()

        if not isinstance(automation_id, str):
            raise TypeError(
                "automation_id must be a string."
            )

        normalized_id = automation_id.strip()

        if not normalized_id:
            raise ValueError(
                "automation_id cannot be empty."
            )

        with self._lock:
            row = self._connection.execute(
                """
                SELECT automation_json
                FROM automations
                WHERE id = ?
                """,
                (normalized_id,),
            ).fetchone()

        if row is None:
            return None

        return self._automation_from_row(row)

    def get_required(
        self,
        automation_id: str,
    ) -> Automation:
        """Return an automation or raise KeyError."""
        automation = self.get(automation_id)

        if automation is None:
            raise KeyError(
                f"Automation does not exist: {automation_id}"
            )

        return automation

    def exists(
        self,
        automation_id: str,
    ) -> bool:
        """Return True when an automation exists."""
        self._ensure_open()

        if not isinstance(automation_id, str):
            return False

        normalized_id = automation_id.strip()

        if not normalized_id:
            return False

        with self._lock:
            row = self._connection.execute(
                """
                SELECT 1
                FROM automations
                WHERE id = ?
                LIMIT 1
                """,
                (normalized_id,),
            ).fetchone()

        return row is not None

    def delete(
        self,
        automation_id: str,
    ) -> bool:
        """
        Delete an automation.

        Associated run-history records are deleted through the foreign
        key's ON DELETE CASCADE behavior.
        """
        self._ensure_open()

        if not isinstance(automation_id, str):
            raise TypeError(
                "automation_id must be a string."
            )

        normalized_id = automation_id.strip()

        if not normalized_id:
            raise ValueError(
                "automation_id cannot be empty."
            )

        with self._lock:
            cursor = self._connection.execute(
                """
                DELETE FROM automations
                WHERE id = ?
                """,
                (normalized_id,),
            )

            self._connection.commit()

        return cursor.rowcount > 0

    def count(self) -> int:
        """Return the total number of stored automations."""
        self._ensure_open()

        with self._lock:
            row = self._connection.execute(
                """
                SELECT COUNT(*) AS total
                FROM automations
                """
            ).fetchone()

        return int(row["total"])

    # ---------------------------------------------------------
    # Automation listing and searching
    # ---------------------------------------------------------

    def list_all(self) -> list[Automation]:
        """Return all automations ordered by name."""
        self._ensure_open()

        with self._lock:
            rows = self._connection.execute(
                """
                SELECT automation_json
                FROM automations
                ORDER BY name COLLATE NOCASE ASC
                """
            ).fetchall()

        return [
            self._automation_from_row(row)
            for row in rows
        ]

    def list_enabled(self) -> list[Automation]:
        """Return all enabled and active automations."""
        self._ensure_open()

        with self._lock:
            rows = self._connection.execute(
                """
                SELECT automation_json
                FROM automations
                WHERE enabled = 1
                  AND status = ?
                ORDER BY name COLLATE NOCASE ASC
                """,
                (
                    self._status_value(
                        AutomationStatus.ACTIVE
                    ),
                ),
            ).fetchall()

        return [
            self._automation_from_row(row)
            for row in rows
        ]

    def list_by_status(
        self,
        status: AutomationStatus | str,
    ) -> list[Automation]:
        """Return all automations with the requested status."""
        self._ensure_open()

        status_value = self._status_value(status)

        with self._lock:
            rows = self._connection.execute(
                """
                SELECT automation_json
                FROM automations
                WHERE status = ?
                ORDER BY name COLLATE NOCASE ASC
                """,
                (status_value,),
            ).fetchall()

        return [
            self._automation_from_row(row)
            for row in rows
        ]

    def search_by_name(
        self,
        query: str,
    ) -> list[Automation]:
        """Perform a case-insensitive automation-name search."""
        self._ensure_open()

        if not isinstance(query, str):
            raise TypeError(
                "Search query must be a string."
            )

        normalized_query = query.strip()

        if not normalized_query:
            return self.list_all()

        pattern = f"%{normalized_query}%"

        with self._lock:
            rows = self._connection.execute(
                """
                SELECT automation_json
                FROM automations
                WHERE name LIKE ? COLLATE NOCASE
                ORDER BY name COLLATE NOCASE ASC
                """,
                (pattern,),
            ).fetchall()

        return [
            self._automation_from_row(row)
            for row in rows
        ]

    # ---------------------------------------------------------
    # Scheduling fields
    # ---------------------------------------------------------

    def update_next_run_time(
        self,
        automation_id: str,
        next_run: datetime | None,
    ) -> None:
        """Update an automation's next scheduled run time."""
        self._ensure_open()

        automation = self.get_required(automation_id)
        automation.next_run = next_run
        automation.updated_at = utc_now()

        self.save(automation)

    def set_enabled(
        self,
        automation_id: str,
        enabled: bool,
    ) -> Automation:
        """Enable or disable an automation."""
        automation = self.get_required(automation_id)
        automation.enabled = bool(enabled)
        automation.updated_at = utc_now()

        self.save(automation)
        return automation

    def set_status(
        self,
        automation_id: str,
        status: AutomationStatus | str,
    ) -> Automation:
        """Update an automation's status."""
        automation = self.get_required(automation_id)

        if isinstance(status, AutomationStatus):
            automation.status = status
        else:
            automation.status = AutomationStatus(
                status.strip().lower()
            )

        automation.updated_at = utc_now()

        self.save(automation)
        return automation

    # ---------------------------------------------------------
    # Run history
    # ---------------------------------------------------------

    def create_run_record(
        self,
        *,
        automation_id: str,
        status: str = "running",
        trigger_source: str | None = None,
        runtime_data: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        started_at: datetime | None = None,
    ) -> int:
        """
        Create an automation execution-history record.

        Returns the new integer run ID.
        """
        self._ensure_open()

        if not self.exists(automation_id):
            raise KeyError(
                f"Automation does not exist: {automation_id}"
            )

        started_at_value = datetime_to_iso(
            started_at
        ) or utc_now_iso()

        runtime_json = json.dumps(
            runtime_data or {},
            ensure_ascii=False,
            default=str,
        )

        metadata_json = json.dumps(
            metadata or {},
            ensure_ascii=False,
            default=str,
        )

        with self._lock:
            cursor = self._connection.execute(
                """
                INSERT INTO automation_runs (
                    automation_id,
                    status,
                    trigger_source,
                    started_at,
                    runtime_data_json,
                    metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    automation_id,
                    str(status),
                    trigger_source,
                    started_at_value,
                    runtime_json,
                    metadata_json,
                ),
            )

            self._connection.commit()

            run_id = cursor.lastrowid

        if run_id is None:
            raise RuntimeError(
                "SQLite did not return a run ID."
            )

        return int(run_id)

    def finish_run_record(
        self,
        run_id: int,
        *,
        status: str,
        stopped_at_phase: str,
        result: dict[str, Any] | None = None,
        error: str | None = None,
        finished_at: datetime | None = None,
    ) -> None:
        """Finish an existing automation run-history record."""
        self._ensure_open()

        finished_at_value = datetime_to_iso(
            finished_at
        ) or utc_now_iso()

        result_json = json.dumps(
            result or {},
            ensure_ascii=False,
            default=str,
        )

        with self._lock:
            cursor = self._connection.execute(
                """
                UPDATE automation_runs
                SET
                    status = ?,
                    stopped_at_phase = ?,
                    finished_at = ?,
                    result_json = ?,
                    error = ?
                WHERE id = ?
                """,
                (
                    str(status),
                    str(stopped_at_phase),
                    finished_at_value,
                    result_json,
                    error,
                    int(run_id),
                ),
            )

            if cursor.rowcount == 0:
                raise KeyError(
                    f"Automation run does not exist: {run_id}"
                )

            self._connection.commit()

    def update_execution_statistics(
        self,
        automation_id: str,
        *,
        last_run: datetime | None = None,
        increment_run_count: bool = True,
    ) -> None:
        """
        Update execution statistics without overwriting the full
        automation JSON with stale data.
        """
        self._ensure_open()

        last_run_value = datetime_to_iso(
            last_run
        ) or utc_now_iso()

        increment = 1 if increment_run_count else 0
        updated_at_value = utc_now_iso()

        with self._lock:
            cursor = self._connection.execute(
                """
                UPDATE automations
                SET
                    last_run = ?,
                    run_count = COALESCE(run_count, 0) + ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    last_run_value,
                    increment,
                    updated_at_value,
                    automation_id,
                ),
            )

            if cursor.rowcount == 0:
                raise KeyError(
                    f"Automation does not exist: {automation_id}"
                )

            row = self._connection.execute(
                """
                SELECT
                    automation_json,
                    run_count
                FROM automations
                WHERE id = ?
                """,
                (automation_id,),
            ).fetchone()

            if row is not None:
                automation_data = parse_json_object(
                    row["automation_json"]
                )

                automation_data["last_run"] = last_run_value
                automation_data["updated_at"] = updated_at_value
                automation_data["run_count"] = int(
                    row["run_count"] or 0
                )

                self._connection.execute(
                    """
                    UPDATE automations
                    SET automation_json = ?
                    WHERE id = ?
                    """,
                    (
                        json.dumps(
                            automation_data,
                            ensure_ascii=False,
                            default=str,
                        ),
                        automation_id,
                    ),
                )

            self._connection.commit()

    def get_run_record(
        self,
        run_id: int,
    ) -> dict[str, Any] | None:
        """Return one execution-history record."""
        self._ensure_open()

        with self._lock:
            row = self._connection.execute(
                """
                SELECT
                    id,
                    automation_id,
                    status,
                    trigger_source,
                    started_at,
                    finished_at,
                    stopped_at_phase,
                    runtime_data_json,
                    metadata_json,
                    result_json,
                    error
                FROM automation_runs
                WHERE id = ?
                """,
                (int(run_id),),
            ).fetchone()

        if row is None:
            return None

        return self._run_row_to_dict(row)

    def list_run_history(
        self,
        *,
        automation_id: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Return recent execution-history records."""
        self._ensure_open()

        if limit < 1:
            raise ValueError(
                "History limit must be at least 1."
            )

        query = """
            SELECT
                id,
                automation_id,
                status,
                trigger_source,
                started_at,
                finished_at,
                stopped_at_phase,
                runtime_data_json,
                metadata_json,
                result_json,
                error
            FROM automation_runs
        """

        parameters: list[Any] = []

        if automation_id is not None:
            query += " WHERE automation_id = ?"
            parameters.append(automation_id)

        query += " ORDER BY id DESC LIMIT ?"
        parameters.append(int(limit))

        with self._lock:
            rows = self._connection.execute(
                query,
                parameters,
            ).fetchall()

        return [
            self._run_row_to_dict(row)
            for row in rows
        ]

    def delete_run_history(
        self,
        *,
        automation_id: str | None = None,
    ) -> int:
        """
        Delete execution history.

        When automation_id is omitted, all history is deleted.
        """
        self._ensure_open()

        with self._lock:
            if automation_id is None:
                cursor = self._connection.execute(
                    """
                    DELETE FROM automation_runs
                    """
                )
            else:
                cursor = self._connection.execute(
                    """
                    DELETE FROM automation_runs
                    WHERE automation_id = ?
                    """,
                    (automation_id,),
                )

            self._connection.commit()

        return int(cursor.rowcount)

    # ---------------------------------------------------------
    # Internal conversion helpers
    # ---------------------------------------------------------

    @staticmethod
    def _automation_from_row(
        row: sqlite3.Row,
    ) -> Automation:
        automation_json = row["automation_json"]

        try:
            automation_data = json.loads(
                automation_json
            )
        except json.JSONDecodeError as error:
            raise ValueError(
                "Stored automation JSON is invalid."
            ) from error

        if not isinstance(automation_data, dict):
            raise ValueError(
                "Stored automation JSON must be an object."
            )

        return Automation.from_dict(
            automation_data
        )

    @staticmethod
    def _run_row_to_dict(
        row: sqlite3.Row,
    ) -> dict[str, Any]:
        return {
            "id": int(row["id"]),
            "automation_id": row["automation_id"],
            "status": row["status"],
            "trigger_source": row["trigger_source"],
            "started_at": row["started_at"],
            "finished_at": row["finished_at"],
            "stopped_at_phase": row[
                "stopped_at_phase"
            ],
            "runtime_data": parse_json_object(
                row["runtime_data_json"]
            ),
            "metadata": parse_json_object(
                row["metadata_json"]
            ),
            "result": parse_json_object(
                row["result_json"]
            ),
            "error": row["error"],
        }

    @staticmethod
    def _status_value(
        status: AutomationStatus | str,
    ) -> str:
        if isinstance(status, AutomationStatus):
            return status.value

        if not isinstance(status, str):
            raise TypeError(
                "Automation status must be a string or "
                "AutomationStatus."
            )

        normalized = status.strip().lower()

        if not normalized:
            raise ValueError(
                "Automation status cannot be empty."
            )

        return normalized

    # ---------------------------------------------------------
    # Connection lifecycle
    # ---------------------------------------------------------

    def close(self) -> None:
        """Close the SQLite connection."""
        if self._closed:
            return

        with self._lock:
            self._connection.close()
            self._closed = True

    def __enter__(self) -> "AutomationStore":
        self._ensure_open()
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: Any,
    ) -> None:
        self.close()