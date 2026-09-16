from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

@dataclass
class EvidenceItem:
    name: str
    value: Any
    source: str
    period_end: Optional[str] = None
    filed_at: Optional[str] = None
    available_at: Optional[str] = None
    authority: str = "UNKNOWN"
    status: str = "UNKNOWN"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self): return asdict(self)

@dataclass
class ResearchSnapshot:
    symbol: str
    as_of: str
    universe_as_of: str
    market_data_as_of: Optional[str]
    evidence: Dict[str, EvidenceItem]
    eligible: bool = True
    exclusion_reasons: List[str] = field(default_factory=list)
    provenance: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self):
        d=asdict(self)
        d["evidence"]={k:v.to_dict() for k,v in self.evidence.items()}
        return d

@dataclass
class BacktestAudit:
    requested_start: str
    requested_end: str
    actual_start: Optional[str]
    actual_end: Optional[str]
    observations: int
    symbols_requested: List[str]
    symbols_used: List[str]
    lookahead_violations: int = 0
    survivorship_mode: str = "POINT_IN_TIME_REQUIRED"
    point_in_time_fundamentals: bool = True
    point_in_time_universe: bool = True
    status: str = "UNKNOWN"
    warnings: List[str] = field(default_factory=list)

@dataclass
class BacktestResult:
    audit: BacktestAudit
    equity_curve: List[Dict[str, float]]
    trades: List[Dict[str, Any]]
    metrics: Dict[str, Optional[float]]
