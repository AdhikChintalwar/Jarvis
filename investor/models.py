from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class RiskLevel(str, Enum):
    VERY_LOW = "very_low"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    VERY_HIGH = "very_high"


class Signal(str, Enum):
    STRONG_BULLISH = "strong_bullish"
    BULLISH = "bullish"
    NEUTRAL = "neutral"
    BEARISH = "bearish"
    STRONG_BEARISH = "strong_bearish"


class EvidenceQuality(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class Evidence:
    metric: str
    value: Any
    source: str
    description: str = ""
    timestamp: str = field(
        default_factory=lambda: datetime.now().isoformat()
    )
    quality: EvidenceQuality = EvidenceQuality.MEDIUM

    def to_dict(self):
        result = asdict(self)
        result["quality"] = self.quality.value
        return result


@dataclass
class TechnicalMetrics:
    price: Optional[float] = None

    sma_20: Optional[float] = None
    sma_50: Optional[float] = None
    sma_200: Optional[float] = None

    ema_9: Optional[float] = None
    ema_20: Optional[float] = None
    ema_50: Optional[float] = None
    ema_200: Optional[float] = None

    rsi_14: Optional[float] = None

    macd: Optional[float] = None
    macd_signal: Optional[float] = None
    macd_histogram: Optional[float] = None

    atr_14: Optional[float] = None
    atr_percent: Optional[float] = None

    bollinger_upper: Optional[float] = None
    bollinger_middle: Optional[float] = None
    bollinger_lower: Optional[float] = None

    vwap: Optional[float] = None
    obv: Optional[float] = None

    relative_volume: Optional[float] = None

    high_52_week: Optional[float] = None
    low_52_week: Optional[float] = None

    distance_from_52_week_high_pct: Optional[float] = None
    distance_from_ema20_pct: Optional[float] = None
    distance_from_ema50_pct: Optional[float] = None
    distance_from_ema200_pct: Optional[float] = None

    trend_signal: Signal = Signal.NEUTRAL
    momentum_signal: Signal = Signal.NEUTRAL


@dataclass
class FundamentalMetrics:
    market_cap: Optional[float] = None

    trailing_pe: Optional[float] = None
    forward_pe: Optional[float] = None
    price_to_sales: Optional[float] = None
    price_to_book: Optional[float] = None

    revenue: Optional[float] = None
    revenue_growth: Optional[float] = None

    net_income: Optional[float] = None

    profit_margin: Optional[float] = None
    operating_margin: Optional[float] = None

    total_cash: Optional[float] = None
    total_debt: Optional[float] = None

    debt_to_equity: Optional[float] = None

    free_cash_flow: Optional[float] = None
    operating_cash_flow: Optional[float] = None

    return_on_equity: Optional[float] = None
    return_on_assets: Optional[float] = None

    beta: Optional[float] = None

    shares_outstanding: Optional[float] = None
    float_shares: Optional[float] = None

    short_ratio: Optional[float] = None
    short_percent_float: Optional[float] = None


@dataclass
class MarketMetrics:
    current_price: Optional[float] = None
    previous_close: Optional[float] = None

    daily_change: Optional[float] = None
    daily_change_pct: Optional[float] = None

    volume: Optional[float] = None
    average_volume: Optional[float] = None

    dollar_volume: Optional[float] = None

    day_high: Optional[float] = None
    day_low: Optional[float] = None

    bid: Optional[float] = None
    ask: Optional[float] = None
    bid_ask_spread_pct: Optional[float] = None


@dataclass
class RiskMetrics:
    overall_risk: RiskLevel = RiskLevel.MODERATE

    annualized_volatility: Optional[float] = None
    max_drawdown: Optional[float] = None

    average_daily_move: Optional[float] = None
    largest_daily_drop: Optional[float] = None
    largest_daily_gain: Optional[float] = None

    liquidity_risk: RiskLevel = RiskLevel.MODERATE
    volatility_risk: RiskLevel = RiskLevel.MODERATE
    trend_risk: RiskLevel = RiskLevel.MODERATE
    gap_risk: RiskLevel = RiskLevel.MODERATE
    overextension_risk: RiskLevel = RiskLevel.MODERATE

    warnings: list[str] = field(default_factory=list)


@dataclass
class ScoreComponent:
    name: str
    score: float
    weight: float
    explanation: str

    @property
    def weighted_score(self):
        return self.score * self.weight


@dataclass
class StockScore:
    overall_score: float = 50.0
    confidence: float = 0.0

    signal: Signal = Signal.NEUTRAL

    components: list[ScoreComponent] = field(default_factory=list)

    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)

    financial_evidence_confidence: float = 0.0
    financial_evidence_coverage: float = 0.0
    gated_financial_metrics: list[str] = field(default_factory=list)


@dataclass
class StockReport:
    ticker: str
    company_name: str

    generated_at: str

    market: MarketMetrics
    technical: TechnicalMetrics
    fundamentals: FundamentalMetrics
    risk: RiskMetrics
    score: StockScore

    evidence: list[Evidence] = field(default_factory=list)

    data_warnings: list[str] = field(default_factory=list)

    def to_dict(self):
        data = asdict(self)

        data["technical"]["trend_signal"] = (
            self.technical.trend_signal.value
        )

        data["technical"]["momentum_signal"] = (
            self.technical.momentum_signal.value
        )

        data["risk"]["overall_risk"] = (
            self.risk.overall_risk.value
        )

        data["risk"]["liquidity_risk"] = (
            self.risk.liquidity_risk.value
        )

        data["risk"]["volatility_risk"] = (
            self.risk.volatility_risk.value
        )

        data["risk"]["trend_risk"] = (
            self.risk.trend_risk.value
        )

        data["risk"]["gap_risk"] = (
            self.risk.gap_risk.value
        )

        data["risk"]["overextension_risk"] = (
            self.risk.overextension_risk.value
        )

        data["score"]["signal"] = self.score.signal.value

        for item in data["evidence"]:
            if hasattr(item.get("quality"), "value"):
                item["quality"] = item["quality"].value

        return data