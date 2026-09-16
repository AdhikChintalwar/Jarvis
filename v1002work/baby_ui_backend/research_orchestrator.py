from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


TERMINAL_FAILURES = {"ERROR", "FAILED", "RESEARCH_FAILED"}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime | None) -> str | None:
    return dt.astimezone(timezone.utc).isoformat() if dt else None


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        s = str(value).replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def normalize_symbol(symbol: str) -> str:
    clean = "".join(c for c in str(symbol or "").upper().strip() if c.isalnum() or c in ".-")
    if not clean or len(clean) > 15:
        raise ValueError("Invalid ticker symbol")
    return clean


@dataclass
class CacheState:
    symbol: str
    status: str
    researched_at: str | None
    age_seconds: float | None
    max_age_seconds: float
    action: str
    report_path: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ResearchOrchestrationError(RuntimeError):
    def __init__(self, message: str, *, symbol: str, stage: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.symbol = symbol
        self.stage = stage
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": "RESEARCH_FAILED",
            "symbol": self.symbol,
            "stage": self.stage,
            "error": str(self),
            "details": self.details,
            "retryable": True,
            "authority": {"AI_SCORING": "0%", "AI_EXECUTION": "NONE", "REAL_MONEY": "DISABLED"},
        }


class ResearchOrchestrator:
    """Owns cache freshness and safe on-demand production research.

    It never scores securities. It only decides whether the persisted production
    research artifact is fresh enough to reuse, waits for/runs ResearchService,
    and returns explicit orchestration metadata.
    """

    def __init__(self, research_service, report_dir: str | Path = "data/ui_research",
                 max_age_seconds: float | None = None, timeout_seconds: float | None = None,
                 poll_seconds: float = 0.5):
        self.research_service = research_service
        self.report_dir = Path(report_dir)
        self.report_dir.mkdir(parents=True, exist_ok=True)
        self.max_age_seconds = float(max_age_seconds if max_age_seconds is not None else os.getenv("BABY_RESEARCH_MAX_AGE_SECONDS", "21600"))
        self.timeout_seconds = float(timeout_seconds if timeout_seconds is not None else os.getenv("BABY_RESEARCH_TIMEOUT_SECONDS", "240"))
        self.poll_seconds = max(0.1, float(poll_seconds))

    def _path(self, symbol: str) -> Path:
        return self.report_dir / f"{symbol}.json"

    def _artifact_time(self, path: Path) -> datetime | None:
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text())
        except Exception:
            data = {}
        # Prefer actual completion/generated timestamps, then filesystem mtime.
        for candidate in (data.get("research_completed_at"), data.get("generated_at"), data.get("updated_at"), data.get("as_of")):
            dt = _parse_dt(candidate)
            if dt:
                return dt
        try:
            return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        except OSError:
            return None

    def inspect(self, symbol: str) -> CacheState:
        symbol = normalize_symbol(symbol)
        path = self._path(symbol)
        researched_at = self._artifact_time(path)
        if not path.exists():
            return CacheState(symbol, "MISSING", None, None, self.max_age_seconds, "CREATE", str(path), "No persisted production research artifact exists.")
        if researched_at is None:
            return CacheState(symbol, "STALE", None, None, self.max_age_seconds, "REFRESH", str(path), "Research artifact exists but its age cannot be established safely.")
        age = max(0.0, (_utcnow() - researched_at).total_seconds())
        if age > self.max_age_seconds:
            return CacheState(symbol, "STALE", _iso(researched_at), round(age, 3), self.max_age_seconds, "REFRESH", str(path), "Persisted research exceeds the configured freshness window.")
        return CacheState(symbol, "FRESH", _iso(researched_at), round(age, 3), self.max_age_seconds, "REUSE", str(path), "Persisted production research is within the freshness window.")

    def ensure(self, symbol: str, *, force: bool = False) -> dict[str, Any]:
        symbol = normalize_symbol(symbol)
        before = self.inspect(symbol)
        if before.status == "FRESH" and not force:
            out = before.to_dict()
            out["action"] = "REUSED"
            return out

        requested_action = "REFRESHED" if before.status != "MISSING" else "CREATED"
        try:
            self.research_service.start(symbol, force=(force or before.status != "MISSING"))
        except Exception as exc:
            raise ResearchOrchestrationError(str(exc), symbol=symbol, stage="START_RESEARCH", details={"cache_before": before.to_dict()}) from exc

        deadline = time.monotonic() + self.timeout_seconds
        last: dict[str, Any] = {}
        while time.monotonic() < deadline:
            last = self.research_service.status(symbol) or {}
            state = str(last.get("status") or "UNKNOWN").upper()
            if state == "READY":
                after = self.inspect(symbol)
                # A READY state is accepted only if the artifact exists and is parseable.
                path = self._path(symbol)
                try:
                    payload = json.loads(path.read_text())
                    if not isinstance(payload, dict) or not payload:
                        raise ValueError("empty research artifact")
                except Exception as exc:
                    raise ResearchOrchestrationError("Research completed but persisted artifact is invalid.", symbol=symbol, stage="VALIDATE_ARTIFACT", details={"job": last, "error": str(exc)}) from exc
                result = after.to_dict()
                result.update({"status": "FRESH", "action": requested_action, "job": last})
                return result
            if state in TERMINAL_FAILURES:
                raise ResearchOrchestrationError(last.get("error") or "Production research failed.", symbol=symbol, stage=str(last.get("stage") or "RESEARCH"), details={"job": last, "cache_before": before.to_dict()})
            time.sleep(self.poll_seconds)

        raise ResearchOrchestrationError(
            f"Production research did not finish within {self.timeout_seconds:.0f} seconds.",
            symbol=symbol,
            stage="TIMEOUT",
            details={"job": last, "cache_before": before.to_dict()},
        )
