from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Literal

Status = Literal['PASS','REVIEW','FAIL','UNKNOWN','STALE','CONFLICT']

@dataclass
class Provenance:
    source: str
    authority: str
    as_of: str | None = None
    verified: bool = False
    status: Status = 'UNKNOWN'
    reference: str | None = None

@dataclass
class Metric:
    key: str
    label: str
    abbreviation: str | None
    value: Any
    unit: str | None = None
    definition: str = ''
    formula: str | None = None
    inputs: dict[str, Any] = field(default_factory=dict)
    interpretation: str = ''
    threshold: str | None = None
    provenance: list[Provenance] = field(default_factory=list)
    status: Status = 'UNKNOWN'

@dataclass
class ResearchStage:
    id: str
    label: str
    status: Status
    score: float | None = None
    summary: str = ''
    metrics: list[Metric] = field(default_factory=list)
    positives: list[str] = field(default_factory=list)
    negatives: list[str] = field(default_factory=list)
    unknowns: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)

@dataclass
class Quote:
    symbol: str
    price: float | None
    change: float | None = None
    change_pct: float | None = None
    bid: float | None = None
    ask: float | None = None
    volume: float | None = None
    day_high: float | None = None
    day_low: float | None = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    quality: Literal['LIVE','DELAYED','STALE','UNKNOWN'] = 'UNKNOWN'
    provider: str = 'UNKNOWN'

@dataclass
class ResearchReport:
    symbol: str
    company_name: str = ''
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    decision: str = 'UNKNOWN'
    score: float | None = None
    confidence: float | None = None
    coverage: float | None = None
    risk: str = 'UNKNOWN'
    hard_risk_override: bool = False
    data_integrity: Status = 'UNKNOWN'
    validation_status: Status = 'UNKNOWN'
    ai_scoring_authority: float = 0.0
    ai_execution_authority: str = 'NONE'
    stages: list[ResearchStage] = field(default_factory=list)
    trade_plan: dict[str, Any] = field(default_factory=dict)
    portfolio_impact: dict[str, Any] = field(default_factory=dict)
    historical_validation: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
