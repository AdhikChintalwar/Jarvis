from __future__ import annotations

import math

import numpy as np
import pandas as pd

from investor.scanner.models import (
    QuantMetrics,
    UniverseStock,
)

from investor.scanner.scan_profiles import (
    ScanProfile,
)

from investor.scanner.volume_flow import (
    VolumeFlowEngine,
)


class QuantitativeFilter:

    def __init__(
        self,
    ):

        self.volume_flow = (
            VolumeFlowEngine()
        )

    def analyze(
        self,
        stock: UniverseStock,
        history: pd.DataFrame,
        profile: ScanProfile,
    ) -> QuantMetrics | None:

        if history is None:
            return None

        df = (
            history
            .copy()
            .dropna(
                subset=["Close"]
            )
        )

        if len(df) < (
            profile.min_history_days
        ):

            return None

        close = (
            df["Close"]
            .astype(float)
        )

        high = (
            df["High"]
            .astype(float)
        )

        low = (
            df["Low"]
            .astype(float)
        )

        if close.empty:
            return None

        price = self._safe(
            close.iloc[-1]
        )

        if price is None:
            return None

        if price < (
            profile.min_price
        ):
            return None

        if (
            profile.max_price
            is not None
            and price
            > profile.max_price
        ):
            return None

        #
        # Volume intelligence
        #

        flow = (
            self.volume_flow
            .analyze(
                df
            )
        )

        average_volume = (
            flow.average_volume_20d
        )

        if (
            average_volume is None
            or average_volume
            < profile.min_avg_volume
        ):

            return None

        average_dollar_volume = (
            flow
            .average_dollar_volume_20d
        )

        if (
            average_dollar_volume
            is None
            or average_dollar_volume
            < profile.min_dollar_volume
        ):

            return None

        #
        # Hard RVOL profile gate
        #

        if (
            profile.min_relative_volume
            is not None
        ):

            if (
                flow.relative_volume
                is None
                or flow.relative_volume
                < profile.min_relative_volume
            ):

                return None

        returns = (
            close
            .pct_change()
            .dropna()
        )

        volatility = None

        if len(returns) >= 20:

            volatility = (
                returns.std()
                * np.sqrt(252)
                * 100
            )

            volatility = (
                self._safe(
                    volatility
                )
            )

        if (
            profile.max_volatility
            is not None
            and volatility
            is not None
            and volatility
            > profile.max_volatility
        ):

            return None

        sma20 = self._safe(
            close
            .rolling(20)
            .mean()
            .iloc[-1]
        )

        sma50 = self._safe(
            close
            .rolling(50)
            .mean()
            .iloc[-1]
        )

        sma200 = self._safe(
            close
            .rolling(200)
            .mean()
            .iloc[-1]
        )

        ema20 = self._safe(
            close
            .ewm(
                span=20,
                adjust=False,
            )
            .mean()
            .iloc[-1]
        )

        ema50 = self._safe(
            close
            .ewm(
                span=50,
                adjust=False,
            )
            .mean()
            .iloc[-1]
        )

        ema200 = self._safe(
            close
            .ewm(
                span=200,
                adjust=False,
            )
            .mean()
            .iloc[-1]
        )

        rsi = (
            self._rsi(
                close
            )
        )

        atr = (
            self._atr(
                high,
                low,
                close,
            )
        )

        atr_pct = None

        if (
            atr is not None
            and price > 0
        ):

            atr_pct = (
                atr
                / price
                * 100
            )

        #
        # Use actual intraday highs/lows
        # for 52-week range.
        #

        high_52 = self._safe(
            high
            .tail(252)
            .max()
        )

        low_52 = self._safe(
            low
            .tail(252)
            .min()
        )

        distance_high = None

        if (
            high_52 is not None
            and high_52 > 0
        ):

            distance_high = (
                (
                    price
                    - high_52
                )
                / high_52
                * 100
            )

        distance_ema20 = (
            self._distance(
                price,
                ema20,
            )
        )

        distance_ema50 = (
            self._distance(
                price,
                ema50,
            )
        )

        max_drawdown = (
            self._max_drawdown(
                close
            )
        )

        metrics = QuantMetrics(

            symbol=(
                stock.symbol
            ),

            provider_symbol=(
                stock.provider_symbol
            ),

            name=(
                stock.name
            ),

            exchange=(
                stock.exchange
            ),

            price=price,

            daily_change_pct=(
                flow.daily_change_pct
            ),

            volume=(
                flow.current_volume
            ),

            average_volume_20d=(
                flow.average_volume_20d
            ),

            relative_volume=(
                flow.relative_volume
            ),

            volume_zscore=(
                flow.volume_zscore
            ),

            current_dollar_volume=(
                flow.current_dollar_volume
            ),

            average_dollar_volume_20d=(
                flow
                .average_dollar_volume_20d
            ),

            #
            # Compatibility field.
            #
            # Dollar volume now means
            # CURRENT dollar volume.
            #

            dollar_volume=(
                flow.current_dollar_volume
            ),

            gap_pct=(
                flow.gap_pct
            ),

            close_location_pct=(
                flow.close_location_pct
            ),

            rvol_3d_average=(
                flow.rvol_3d_average
            ),

            high_volume_days_5d=(
                flow.high_volume_days_5d
            ),

            up_down_volume_ratio_20d=(
                flow
                .up_down_volume_ratio_20d
            ),

            breakout_20d=(
                flow.breakout_20d
            ),

            breakdown_20d=(
                flow.breakdown_20d
            ),

            obv_change_10d_pct=(
                flow.obv_change_10d_pct
            ),

            flow_score=(
                flow.flow_score
            ),

            flow_type=(
                flow.flow_type
            ),

            return_5d_pct=(
                self._period_return(
                    close,
                    5,
                )
            ),

            return_20d_pct=(
                self._period_return(
                    close,
                    20,
                )
            ),

            return_60d_pct=(
                self._period_return(
                    close,
                    60,
                )
            ),

            sma_20=sma20,
            sma_50=sma50,
            sma_200=sma200,

            ema_20=ema20,
            ema_50=ema50,
            ema_200=ema200,

            distance_ema20_pct=(
                distance_ema20
            ),

            distance_ema50_pct=(
                distance_ema50
            ),

            distance_52w_high_pct=(
                distance_high
            ),

            rsi_14=rsi,

            atr_14=atr,
            atr_pct=atr_pct,

            annualized_volatility=(
                volatility
            ),

            max_drawdown_pct=(
                max_drawdown
            ),

            high_52w=(
                high_52
            ),

            low_52w=(
                low_52
            ),
        )

        if flow.flags:

            metrics.flags.extend(
                flow.flags
            )

        return metrics

    def _rsi(
        self,
        close,
        period=14,
    ):

        delta = (
            close.diff()
        )

        gain = (
            delta.clip(
                lower=0
            )
        )

        loss = (
            -delta.clip(
                upper=0
            )
        )

        avg_gain = (
            gain
            .ewm(
                alpha=1 / period,
                adjust=False,
            )
            .mean()
        )

        avg_loss = (
            loss
            .ewm(
                alpha=1 / period,
                adjust=False,
            )
            .mean()
        )

        rs = (
            avg_gain
            / avg_loss.replace(
                0,
                np.nan,
            )
        )

        rsi = (
            100
            - (
                100
                / (
                    1 + rs
                )
            )
        )

        return self._safe(
            rsi.iloc[-1]
        )

    def _atr(
        self,
        high,
        low,
        close,
        period=14,
    ):

        previous_close = (
            close.shift(1)
        )

        true_range = pd.concat(
            [
                high - low,

                (
                    high
                    - previous_close
                ).abs(),

                (
                    low
                    - previous_close
                ).abs(),
            ],
            axis=1,
        ).max(
            axis=1
        )

        atr = (
            true_range
            .ewm(
                alpha=1 / period,
                adjust=False,
            )
            .mean()
        )

        return self._safe(
            atr.iloc[-1]
        )

    def _max_drawdown(
        self,
        close,
    ):

        running_max = (
            close.cummax()
        )

        drawdown = (
            close
            / running_max
            - 1
        )

        value = (
            abs(
                drawdown.min()
            )
            * 100
        )

        return self._safe(
            value
        )

    def _period_return(
        self,
        close,
        days,
    ):

        if len(close) <= days:
            return None

        previous = self._safe(
            close.iloc[
                -(days + 1)
            ]
        )

        current = self._safe(
            close.iloc[-1]
        )

        if (
            previous is None
            or current is None
            or previous == 0
        ):

            return None

        return (
            (
                current
                / previous
                - 1
            )
            * 100
        )

    def _distance(
        self,
        price,
        reference,
    ):

        if (
            reference is None
            or reference == 0
        ):

            return None

        return (
            (
                price
                - reference
            )
            / reference
            * 100
        )

    def _safe(
        self,
        value,
    ):

        try:

            value = float(
                value
            )

        except Exception:

            return None

        if (
            math.isnan(value)
            or math.isinf(value)
        ):

            return None

        return value