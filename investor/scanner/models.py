from __future__ import annotations

from dataclasses import (
    asdict,
    dataclass,
    field,
)

from datetime import datetime

from typing import Any


@dataclass
class UniverseStock:

    symbol: str
    provider_symbol: str

    name: str
    exchange: str

    is_etf: bool = False
    is_test_issue: bool = False


@dataclass
class QuantMetrics:

    symbol: str
    provider_symbol: str

    name: str
    exchange: str

    price: float | None = None

    daily_change_pct: float | None = None

    volume: float | None = None

    average_volume_20d: float | None = None

    relative_volume: float | None = None

    volume_zscore: float | None = None

    current_dollar_volume: float | None = None

    average_dollar_volume_20d: float | None = None

    gap_pct: float | None = None

    close_location_pct: float | None = None

    rvol_3d_average: float | None = None

    high_volume_days_5d: int = 0

    up_down_volume_ratio_20d: float | None = None

    breakout_20d: bool = False
    breakdown_20d: bool = False

    obv_change_10d_pct: float | None = None

    flow_score: float = 50
    flow_type: str = "NEUTRAL"

    dollar_volume: float | None = None

    return_5d_pct: float | None = None
    return_20d_pct: float | None = None
    return_60d_pct: float | None = None

    sma_20: float | None = None
    sma_50: float | None = None
    sma_200: float | None = None

    ema_20: float | None = None
    ema_50: float | None = None
    ema_200: float | None = None

    distance_ema20_pct: float | None = None
    distance_ema50_pct: float | None = None

    distance_52w_high_pct: float | None = None

    rsi_14: float | None = None

    atr_14: float | None = None
    atr_pct: float | None = None

    annualized_volatility: float | None = None
    max_drawdown_pct: float | None = None

    high_52w: float | None = None
    low_52w: float | None = None

    trend_score: float = 0
    momentum_score: float = 0
    volume_score: float = 0
    risk_score: float = 0
    setup_score: float = 0

    opportunity_score: float = 0

    scan_profile: str = ""

    flags: list[str] = field(
        default_factory=list
    )

    rejection_reason: str | None = None

    def to_dict(
        self,
    ) -> dict[str, Any]:

        return asdict(
            self
        )


@dataclass
class DeepCandidate:

    symbol: str
    scan_score: float

    decision: str

    stock_type: str
    trading_profile: str

    financial_health: float | None
    data_quality: float | None

    risk: str
    dilution_risk: str

    price: float | None

    rsi: float | None

    relative_volume: float | None

    reasons: list[str] = field(
        default_factory=list
    )

    def to_dict(
        self,
    ):

        return asdict(
            self
        )


@dataclass
class ScanSummary:

    profile: str

    generated_at: str = field(
        default_factory=lambda: (
            datetime.now().isoformat()
        )
    )

    universe_count: int = 0

    market_data_count: int = 0

    eligibility_count: int = 0

    quantitative_count: int = 0

    deep_analysis_count: int = 0

    candidates: list[QuantMetrics] = field(
        default_factory=list
    )

    deep_candidates: list[DeepCandidate] = field(
        default_factory=list
    )

    errors: list[str] = field(
        default_factory=list
    )

    def to_dict(
        self,
    ):

        return {

            "profile":
                self.profile,

            "generated_at":
                self.generated_at,

            "universe_count":
                self.universe_count,

            "market_data_count":
                self.market_data_count,

            "eligibility_count":
                self.eligibility_count,

            "quantitative_count":
                self.quantitative_count,

            "deep_analysis_count":
                self.deep_analysis_count,

            "candidates": [
                candidate.to_dict()
                for candidate
                in self.candidates
            ],

            "deep_candidates": [
                candidate.to_dict()
                for candidate
                in self.deep_candidates
            ],

            "errors":
                self.errors,
        }