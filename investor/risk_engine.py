from __future__ import annotations

import numpy as np
import pandas as pd

from investor.models import (
    MarketMetrics,
    RiskLevel,
    RiskMetrics,
    TechnicalMetrics,
)


class RiskEngine:

    def analyze(
        self,
        history: pd.DataFrame,
        market: MarketMetrics,
        technical: TechnicalMetrics,
    ) -> RiskMetrics:

        close = (
            history["Close"]
            .astype(float)
        )

        open_price = (
            history["Open"]
            .astype(float)
        )

        returns = (
            close
            .pct_change()
            .dropna()
        )

        annualized_volatility = None

        if not returns.empty:

            annualized_volatility = (
                returns.std()
                * np.sqrt(252)
                * 100
            )

        cumulative = (
            1 + returns
        ).cumprod()

        running_max = (
            cumulative.cummax()
        )

        drawdown = (
            cumulative
            / running_max
            - 1
        )

        max_drawdown = None

        if not drawdown.empty:

            max_drawdown = (
                abs(
                    drawdown.min()
                )
                * 100
            )

        average_daily_move = None
        largest_daily_drop = None
        largest_daily_gain = None

        if not returns.empty:

            average_daily_move = (
                returns.abs()
                .mean()
                * 100
            )

            largest_daily_drop = (
                returns.min()
                * 100
            )

            largest_daily_gain = (
                returns.max()
                * 100
            )

        gaps = (
            open_price
            / close.shift(1)
            - 1
        ).dropna()

        average_gap = (
            gaps.abs()
            .mean()
            * 100

            if not gaps.empty
            else None
        )

        liquidity_risk = (
            self._liquidity_risk(
                market
            )
        )

        volatility_risk = (
            self._volatility_risk(
                annualized_volatility
            )
        )

        trend_risk = (
            self._trend_risk(
                technical
            )
        )

        gap_risk = (
            self._gap_risk(
                average_gap
            )
        )

        overextension_risk = (
            self._overextension_risk(
                technical
            )
        )

        warnings = []

        if (
            annualized_volatility
            is not None
            and annualized_volatility
            >= 100
        ):

            warnings.append(
                "Extreme historical volatility."
            )

        elif (
            annualized_volatility
            is not None
            and annualized_volatility
            >= 60
        ):

            warnings.append(
                "Historical volatility is high."
            )

        if (
            max_drawdown
            is not None
            and max_drawdown >= 50
        ):

            warnings.append(
                "Historical maximum drawdown "
                "exceeds 50%."
            )

        if liquidity_risk in {
            RiskLevel.HIGH,
            RiskLevel.VERY_HIGH,
        }:

            warnings.append(
                "Liquidity may create significant "
                "spread and slippage risk."
            )

        if technical.rsi_14 is not None:

            if technical.rsi_14 >= 75:

                warnings.append(
                    "RSI is highly extended."
                )

            elif technical.rsi_14 <= 25:

                warnings.append(
                    "RSI is deeply oversold."
                )

        if (
            technical
            .distance_from_ema20_pct
            is not None
            and abs(
                technical
                .distance_from_ema20_pct
            )
            > 12
        ):

            warnings.append(
                "Price is far from its "
                "20-day EMA."
            )

        overall = (
            self._overall_risk(
                risks=[
                    liquidity_risk,
                    volatility_risk,
                    trend_risk,
                    gap_risk,
                    overextension_risk,
                ],

                annualized_volatility=(
                    annualized_volatility
                ),

                max_drawdown=(
                    max_drawdown
                ),

                atr_percent=(
                    technical
                    .atr_percent
                ),
            )
        )

        return RiskMetrics(

            overall_risk=overall,

            annualized_volatility=(
                float(
                    annualized_volatility
                )

                if annualized_volatility
                is not None

                else None
            ),

            max_drawdown=(
                float(
                    max_drawdown
                )

                if max_drawdown
                is not None

                else None
            ),

            average_daily_move=(
                float(
                    average_daily_move
                )

                if average_daily_move
                is not None

                else None
            ),

            largest_daily_drop=(
                float(
                    largest_daily_drop
                )

                if largest_daily_drop
                is not None

                else None
            ),

            largest_daily_gain=(
                float(
                    largest_daily_gain
                )

                if largest_daily_gain
                is not None

                else None
            ),

            liquidity_risk=(
                liquidity_risk
            ),

            volatility_risk=(
                volatility_risk
            ),

            trend_risk=(
                trend_risk
            ),

            gap_risk=(
                gap_risk
            ),

            overextension_risk=(
                overextension_risk
            ),

            warnings=warnings,
        )

    def _liquidity_risk(
        self,
        market,
    ):

        dollar_volume = (
            market.dollar_volume
        )

        if dollar_volume is None:
            return RiskLevel.MODERATE

        if dollar_volume < 1_000_000:
            return RiskLevel.VERY_HIGH

        if dollar_volume < 5_000_000:
            return RiskLevel.HIGH

        if dollar_volume < 20_000_000:
            return RiskLevel.MODERATE

        if dollar_volume < 100_000_000:
            return RiskLevel.LOW

        return RiskLevel.VERY_LOW

    def _volatility_risk(
        self,
        volatility,
    ):

        if volatility is None:
            return RiskLevel.MODERATE

        if volatility >= 120:
            return RiskLevel.VERY_HIGH

        if volatility >= 70:
            return RiskLevel.HIGH

        if volatility >= 40:
            return RiskLevel.MODERATE

        if volatility >= 20:
            return RiskLevel.LOW

        return RiskLevel.VERY_LOW

    def _trend_risk(
        self,
        technical,
    ):

        value = (
            technical
            .trend_signal
            .value
        )

        if value == "strong_bearish":
            return RiskLevel.VERY_HIGH

        if value == "bearish":
            return RiskLevel.HIGH

        if value == "neutral":
            return RiskLevel.MODERATE

        return RiskLevel.LOW

    def _gap_risk(
        self,
        average_gap,
    ):

        if average_gap is None:
            return RiskLevel.MODERATE

        if average_gap >= 5:
            return RiskLevel.VERY_HIGH

        if average_gap >= 3:
            return RiskLevel.HIGH

        if average_gap >= 1.5:
            return RiskLevel.MODERATE

        return RiskLevel.LOW

    def _overextension_risk(
        self,
        technical,
    ):

        distance = (
            technical
            .distance_from_ema20_pct
        )

        if distance is None:
            return RiskLevel.MODERATE

        distance = abs(
            distance
        )

        if distance >= 20:
            return RiskLevel.VERY_HIGH

        if distance >= 12:
            return RiskLevel.HIGH

        if distance >= 7:
            return RiskLevel.MODERATE

        return RiskLevel.LOW

    def _overall_risk(
        self,
        risks,
        annualized_volatility,
        max_drawdown,
        atr_percent,
    ):

        # HARD RISK OVERRIDES

        if (
            annualized_volatility
            is not None
            and annualized_volatility
            >= 150
        ):

            return RiskLevel.VERY_HIGH

        if (
            max_drawdown
            is not None
            and max_drawdown >= 70
        ):

            return RiskLevel.VERY_HIGH

        if (
            atr_percent
            is not None
            and atr_percent >= 12
        ):

            return RiskLevel.VERY_HIGH

        if (
            annualized_volatility
            is not None
            and annualized_volatility
            >= 90
        ):

            return RiskLevel.HIGH

        if (
            max_drawdown
            is not None
            and max_drawdown >= 50
        ):

            return RiskLevel.HIGH

        score_map = {

            RiskLevel.VERY_LOW: 1,

            RiskLevel.LOW: 2,

            RiskLevel.MODERATE: 3,

            RiskLevel.HIGH: 4,

            RiskLevel.VERY_HIGH: 5,
        }

        average = sum(
            score_map[risk]
            for risk
            in risks
        ) / len(risks)

        if average >= 4.25:
            return RiskLevel.VERY_HIGH

        if average >= 3.5:
            return RiskLevel.HIGH

        if average >= 2.6:
            return RiskLevel.MODERATE

        if average >= 1.7:
            return RiskLevel.LOW

        return RiskLevel.VERY_LOW