from __future__ import annotations

from dataclasses import (
    asdict,
    dataclass,
    field,
)


@dataclass
class AnalystVerdict:
    symbol: str

    decision: str = "INSUFFICIENT_DATA"

    conviction: float = 0.0

    evidence_quality: float = 0.0

    thesis: str = ""

    bull_case: list[str] = field(
        default_factory=list
    )

    bear_case: list[str] = field(
        default_factory=list
    )

    key_risks: list[str] = field(
        default_factory=list
    )

    catalysts: list[str] = field(
        default_factory=list
    )

    entry_view: str = ""

    invalidation: str = ""

    missing_information: list[str] = field(
        default_factory=list
    )

    reasoning_summary: str = ""

    raw: dict = field(
        default_factory=dict
    )

    def to_dict(
        self,
    ):
        return asdict(
            self
        )


@dataclass
class CriticVerdict:
    symbol: str

    thesis_survives: bool = False

    adjusted_conviction: float = 0.0

    strongest_objection: str = ""

    hidden_risks: list[str] = field(
        default_factory=list
    )

    unsupported_claims: list[str] = field(
        default_factory=list
    )

    contradictions: list[str] = field(
        default_factory=list
    )

    what_would_change_view: list[str] = field(
        default_factory=list
    )

    final_warning: str = ""

    raw: dict = field(
        default_factory=dict
    )

    def to_dict(
        self,
    ):
        return asdict(
            self
        )


@dataclass
class CandidateIntelligence:
    symbol: str

    scanner_score: float = 0.0

    flow_score: float = 0.0

    evidence: dict = field(
        default_factory=dict
    )

    analyst: AnalystVerdict | None = None

    critic: CriticVerdict | None = None

    final_candidate_score: float = 0.0

    passed_gate: bool = False

    gate_reasons: list[str] = field(
        default_factory=list
    )

    error: str | None = None

    def to_dict(
        self,
    ):
        return asdict(
            self
        )


@dataclass
class CommitteeRanking:
    symbol: str

    rank: int = 0

    committee_score: float = 0.0

    deterministic_score: float = 50.0
    llm_score: float | None = 0.0
    llm_weight: float = 0.0
    evidence_authority: float = 0.0
    module_coverage: float = 0.0
    governance_status: str = "UNKNOWN"
    maximum_decision: str = "TOP_CANDIDATE"
    governance_constraints: list[str] = field(default_factory=list)
    deterministic_modules: dict = field(default_factory=dict)

    decision: str = "WATCH"

    confidence: float = 0.0

    why_ranked_here: str = ""

    strongest_strength: str = ""

    biggest_risk: str = ""

    preferred_action: str = ""

    integrity_passed: bool = True

    integrity_score: float = 100.0

    supported_claims: list[dict] = field(
        default_factory=list
    )

    unsupported_claims: list[dict] = field(
        default_factory=list
    )

    unknowns: list[str] = field(
        default_factory=list
    )

    evidence_used: list[str] = field(
        default_factory=list
    )

    raw: dict = field(
        default_factory=dict
    )

    def to_dict(
        self,
    ):
        return asdict(
            self
        )


@dataclass
class CommitteeReport:
    profile: str

    source_scan: str

    candidates_processed: int = 0

    candidates_passed: int = 0

    rankings: list[
        CommitteeRanking | dict
    ] = field(
        default_factory=list
    )

    market_summary: str = ""

    committee_summary: str = ""

    avoid_list: list[str] = field(
        default_factory=list
    )

    watch_list: list[str] = field(
        default_factory=list
    )

    errors: list[str] = field(
        default_factory=list
    )

    schema_version: str = "2.3"

    def to_dict(
        self,
    ):
        return asdict(
            self
        )