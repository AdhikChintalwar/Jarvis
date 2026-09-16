from __future__ import annotations

import numpy as np
import pandas as pd

from investor.models import (
    Signal,
    TechnicalMetrics,
)


class TechnicalIndicatorEngine:

    @staticmethod
    def sma(
        series: pd.Series,
        period: int,
    ):
        return series.rolling(period).mean()

    @staticmethod
    def ema(
        series: pd.Series,
        period: int,
    ):
        return series.ewm(
            span=period,
            adjust=False,
        ).mean()

    @staticmethod
    def rsi(
        close: pd.Series,
        period: int = 14,
    ):

        delta = close.diff()

        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)

        avg_gain = gain.ewm(
            alpha=1 / period,
            adjust=False,
        ).mean()

        avg_loss = loss.ewm(
            alpha=1 / period,
            adjust=False,
        ).mean()

        rs = avg_gain / avg_loss.replace(0, np.nan)

        rsi = 100 - (
            100 / (1 + rs)
        )

        return rsi

    @staticmethod
    def macd(
        close: pd.Series,
    ):

        ema12 = close.ewm(
            span=12,
            adjust=False,
        ).mean()

        ema26 = close.ewm(
            span=26,
            adjust=False,
        ).mean()

        macd_line = ema12 - ema26

        signal_line = macd_line.ewm(
            span=9,
            adjust=False,
        ).mean()

        histogram = (
            macd_line - signal_line
        )

        return (
            macd_line,
            signal_line,
            histogram,
        )

    @staticmethod
    def atr(
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        period: int = 14,
    ):

        previous_close = close.shift(1)

        true_range = pd.concat(
            [
                high - low,
                (high - previous_close).abs(),
                (low - previous_close).abs(),
            ],
            axis=1,
        ).max(axis=1)

        return true_range.rolling(
            period
        ).mean()

    @staticmethod
    def bollinger_bands(
        close: pd.Series,
        period: int = 20,
        std_dev: float = 2.0,
    ):

        middle = close.rolling(
            period
        ).mean()

        std = close.rolling(
            period
        ).std()

        upper = middle + std_dev * std
        lower = middle - std_dev * std

        return upper, middle, lower

    @staticmethod
    def obv(
        close: pd.Series,
        volume: pd.Series,
    ):

        direction = np.sign(
            close.diff()
        ).fillna(0)

        return (
            direction * volume
        ).cumsum()

    @staticmethod
    def vwap(
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        volume: pd.Series,
    ):

        typical_price = (
            high + low + close
        ) / 3

        cumulative_value = (
            typical_price * volume
        ).cumsum()

        cumulative_volume = (
            volume.cumsum()
        ).replace(0, np.nan)

        return (
            cumulative_value /
            cumulative_volume
        )

    @staticmethod
    def safe_last(
        series: pd.Series,
    ):

        if (
            series is None
            or series.empty
        ):
            return None

        value = series.iloc[-1]

        if pd.isna(value):
            return None

        return float(value)

    def analyze(
        self,
        history: pd.DataFrame,
    ) -> TechnicalMetrics:

        df = history.copy()

        close = df["Close"].astype(float)
        high = df["High"].astype(float)
        low = df["Low"].astype(float)
        volume = df["Volume"].astype(float)

        current_price = float(
            close.iloc[-1]
        )

        sma20 = self.sma(close, 20)
        sma50 = self.sma(close, 50)
        sma200 = self.sma(close, 200)

        ema9 = self.ema(close, 9)
        ema20 = self.ema(close, 20)
        ema50 = self.ema(close, 50)
        ema200 = self.ema(close, 200)

        rsi14 = self.rsi(close, 14)

        (
            macd_line,
            macd_signal,
            macd_hist,
        ) = self.macd(close)

        atr14 = self.atr(
            high,
            low,
            close,
            14,
        )

        (
            bb_upper,
            bb_middle,
            bb_lower,
        ) = self.bollinger_bands(close)

        obv = self.obv(
            close,
            volume,
        )

        vwap = self.vwap(
            high,
            low,
            close,
            volume,
        )

        avg_volume_20 = (
            volume
            .rolling(20)
            .mean()
        )

        if (
            len(avg_volume_20)
            and avg_volume_20.iloc[-1]
            and not pd.isna(
                avg_volume_20.iloc[-1]
            )
        ):
            relative_volume = (
                volume.iloc[-1]
                / avg_volume_20.iloc[-1]
            )
        else:
            relative_volume = None

        high_52 = (
            close.tail(252).max()
        )

        low_52 = (
            close.tail(252).min()
        )

        def percent_distance(
            current,
            reference,
        ):
            if not reference:
                return None

            return (
                (
                    current - reference
                )
                / reference
                * 100
            )

        trend_signal = self._trend_signal(
            current_price=current_price,
            ema20=self.safe_last(ema20),
            ema50=self.safe_last(ema50),
            ema200=self.safe_last(ema200),
        )

        momentum_signal = (
            self._momentum_signal(
                rsi=self.safe_last(rsi14),
                macd_hist=self.safe_last(
                    macd_hist
                ),
            )
        )

        atr_value = self.safe_last(
            atr14
        )

        atr_percent = None

        if (
            atr_value is not None
            and current_price
        ):
            atr_percent = (
                atr_value /
                current_price *
                100
            )

        return TechnicalMetrics(
            price=current_price,

            sma_20=self.safe_last(sma20),
            sma_50=self.safe_last(sma50),
            sma_200=self.safe_last(sma200),

            ema_9=self.safe_last(ema9),
            ema_20=self.safe_last(ema20),
            ema_50=self.safe_last(ema50),
            ema_200=self.safe_last(ema200),

            rsi_14=self.safe_last(rsi14),

            macd=self.safe_last(
                macd_line
            ),

            macd_signal=self.safe_last(
                macd_signal
            ),

            macd_histogram=self.safe_last(
                macd_hist
            ),

            atr_14=atr_value,
            atr_percent=atr_percent,

            bollinger_upper=self.safe_last(
                bb_upper
            ),

            bollinger_middle=self.safe_last(
                bb_middle
            ),

            bollinger_lower=self.safe_last(
                bb_lower
            ),

            vwap=self.safe_last(vwap),
            obv=self.safe_last(obv),

            relative_volume=(
                float(relative_volume)
                if relative_volume is not None
                else None
            ),

            high_52_week=float(
                high_52
            ),

            low_52_week=float(
                low_52
            ),

            distance_from_52_week_high_pct=(
                percent_distance(
                    current_price,
                    high_52,
                )
            ),

            distance_from_ema20_pct=(
                percent_distance(
                    current_price,
                    self.safe_last(
                        ema20
                    ),
                )
            ),

            distance_from_ema50_pct=(
                percent_distance(
                    current_price,
                    self.safe_last(
                        ema50
                    ),
                )
            ),

            distance_from_ema200_pct=(
                percent_distance(
                    current_price,
                    self.safe_last(
                        ema200
                    ),
                )
            ),

            trend_signal=trend_signal,
            momentum_signal=(
                momentum_signal
            ),
        )

    def _trend_signal(
        self,
        current_price,
        ema20,
        ema50,
        ema200,
    ) -> Signal:

        if None in (
            current_price,
            ema20,
            ema50,
        ):
            return Signal.NEUTRAL

        if (
            ema200 is not None
            and current_price > ema20
            and ema20 > ema50
            and ema50 > ema200
        ):
            return (
                Signal.STRONG_BULLISH
            )

        if (
            current_price > ema20
            and ema20 > ema50
        ):
            return Signal.BULLISH

        if (
            ema200 is not None
            and current_price < ema20
            and ema20 < ema50
            and ema50 < ema200
        ):
            return (
                Signal.STRONG_BEARISH
            )

        if (
            current_price < ema20
            and ema20 < ema50
        ):
            return Signal.BEARISH

        return Signal.NEUTRAL

    def _momentum_signal(
        self,
        rsi,
        macd_hist,
    ) -> Signal:

        if (
            rsi is None
            or macd_hist is None
        ):
            return Signal.NEUTRAL

        if (
            55 <= rsi <= 70
            and macd_hist > 0
        ):
            return Signal.BULLISH

        if (
            rsi > 70
            and macd_hist > 0
        ):
            return Signal.NEUTRAL

        if (
            30 <= rsi <= 45
            and macd_hist < 0
        ):
            return Signal.BEARISH

        if (
            rsi < 30
            and macd_hist < 0
        ):
            return Signal.NEUTRAL

        return Signal.NEUTRAL