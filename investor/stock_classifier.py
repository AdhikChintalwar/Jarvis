from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class StockType(str, Enum):
    MEGA_CAP = "mega_cap"
    LARGE_CAP = "large_cap"
    MID_CAP = "mid_cap"
    SMALL_CAP = "small_cap"
    MICRO_CAP = "micro_cap"
    NANO_CAP = "nano_cap"
    UNKNOWN = "unknown"


class TradingProfile(str, Enum):
    STABLE = "stable"
    GROWTH = "growth"
    MOMENTUM = "momentum"
    HIGH_VOLATILITY = "high_volatility"
    SPECULATIVE = "speculative"
    UNKNOWN = "unknown"


@dataclass
class StockClassification:
    stock_type: StockType
    trading_profile: TradingProfile

    market_cap: Optional[float]

    is_low_float: bool
    is_high_volatility: bool
    is_speculative: bool

    description: str


class StockClassifier:

    LOW_FLOAT_THRESHOLD = 20_000_000

    def classify(
        self,
        market_cap: Optional[float],
        float_shares: Optional[float],
        annualized_volatility: Optional[float],
        revenue_growth: Optional[float] = None,
        profitable: Optional[bool] = None,
    ) -> StockClassification:

        stock_type = self._market_cap_type(
            market_cap
        )

        is_low_float = (
            float_shares is not None
            and float_shares
            < self.LOW_FLOAT_THRESHOLD
        )

        is_high_volatility = (
            annualized_volatility is not None
            and annualized_volatility >= 60
        )

        is_speculative = (
            stock_type in {
                StockType.MICRO_CAP,
                StockType.NANO_CAP,
            }
            or is_low_float
            or (
                annualized_volatility is not None
                and annualized_volatility >= 100
            )
        )

        trading_profile = (
            self._trading_profile(
                stock_type=stock_type,
                annualized_volatility=annualized_volatility,
                revenue_growth=revenue_growth,
                profitable=profitable,
                is_low_float=is_low_float,
            )
        )

        description = self._description(
            stock_type,
            trading_profile,
            is_low_float,
            is_high_volatility,
        )

        return StockClassification(
            stock_type=stock_type,
            trading_profile=trading_profile,
            market_cap=market_cap,
            is_low_float=is_low_float,
            is_high_volatility=is_high_volatility,
            is_speculative=is_speculative,
            description=description,
        )

    def _market_cap_type(
        self,
        market_cap,
    ) -> StockType:

        if market_cap is None:
            return StockType.UNKNOWN

        if market_cap >= 200_000_000_000:
            return StockType.MEGA_CAP

        if market_cap >= 10_000_000_000:
            return StockType.LARGE_CAP

        if market_cap >= 2_000_000_000:
            return StockType.MID_CAP

        if market_cap >= 300_000_000:
            return StockType.SMALL_CAP

        if market_cap >= 50_000_000:
            return StockType.MICRO_CAP

        return StockType.NANO_CAP

    def _trading_profile(
        self,
        stock_type,
        annualized_volatility,
        revenue_growth,
        profitable,
        is_low_float,
    ) -> TradingProfile:

        if (
            annualized_volatility is not None
            and annualized_volatility >= 120
        ):
            return TradingProfile.SPECULATIVE

        if is_low_float:
            return TradingProfile.SPECULATIVE

        if (
            annualized_volatility is not None
            and annualized_volatility >= 60
        ):
            return TradingProfile.HIGH_VOLATILITY

        if (
            revenue_growth is not None
            and revenue_growth >= 0.20
        ):
            return TradingProfile.GROWTH

        if (
            annualized_volatility is not None
            and annualized_volatility >= 35
        ):
            return TradingProfile.MOMENTUM

        if profitable:
            return TradingProfile.STABLE

        return TradingProfile.UNKNOWN

    def _description(
        self,
        stock_type,
        profile,
        low_float,
        high_volatility,
    ):

        flags = []

        if low_float:
            flags.append("low-float")

        if high_volatility:
            flags.append("high-volatility")

        flags.append(
            profile.value.replace("_", "-")
        )

        return (
            f"{stock_type.value.replace('_', '-')} / "
            + " / ".join(flags)
        )