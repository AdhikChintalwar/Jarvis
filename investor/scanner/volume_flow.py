from __future__ import annotations

from dataclasses import dataclass

import math
import numpy as np
import pandas as pd


@dataclass
class VolumeFlowMetrics:

    relative_volume: float | None = None
    volume_zscore: float | None = None

    current_volume: float | None = None
    average_volume_20d: float | None = None

    current_dollar_volume: float | None = None
    average_dollar_volume_20d: float | None = None

    daily_change_pct: float | None = None
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

    flags: list[str] | None = None


class VolumeFlowEngine:

    def analyze(
        self,
        history: pd.DataFrame,
    ) -> VolumeFlowMetrics:

        if history is None or len(history) < 25:
            return VolumeFlowMetrics(
                flags=["INSUFFICIENT_HISTORY"]
            )

        df = history.copy()

        open_ = (
            df["Open"]
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

        close = (
            df["Close"]
            .astype(float)
        )

        volume = (
            df["Volume"]
            .astype(float)
        )

        current_close = self._safe(
            close.iloc[-1]
        )

        current_open = self._safe(
            open_.iloc[-1]
        )

        current_high = self._safe(
            high.iloc[-1]
        )

        current_low = self._safe(
            low.iloc[-1]
        )

        current_volume = self._safe(
            volume.iloc[-1]
        )

        previous_close = self._safe(
            close.iloc[-2]
        )

        #
        # IMPORTANT:
        #
        # Today's volume is NOT included
        # in the baseline.
        #

        prior_volume = (
            volume.iloc[-21:-1]
            .dropna()
        )

        average_volume_20d = self._safe(
            prior_volume.mean()
        )

        volume_std_20d = self._safe(
            prior_volume.std()
        )

        relative_volume = None

        if (
            current_volume is not None
            and average_volume_20d is not None
            and average_volume_20d > 0
        ):

            relative_volume = (
                current_volume
                / average_volume_20d
            )

        volume_zscore = None

        if (
            current_volume is not None
            and average_volume_20d is not None
            and volume_std_20d is not None
            and volume_std_20d > 0
        ):

            volume_zscore = (
                current_volume
                - average_volume_20d
            ) / volume_std_20d

        #
        # Dollar volume
        #

        current_dollar_volume = None

        if (
            current_close is not None
            and current_volume is not None
        ):

            current_dollar_volume = (
                current_close
                * current_volume
            )

        prior_dollar_volume = (
            close.iloc[-21:-1]
            * volume.iloc[-21:-1]
        )

        average_dollar_volume_20d = (
            self._safe(
                prior_dollar_volume.mean()
            )
        )

        #
        # Daily price move
        #

        daily_change_pct = None

        if (
            current_close is not None
            and previous_close is not None
            and previous_close > 0
        ):

            daily_change_pct = (
                (
                    current_close
                    / previous_close
                )
                - 1
            ) * 100

        #
        # Gap
        #

        gap_pct = None

        if (
            current_open is not None
            and previous_close is not None
            and previous_close > 0
        ):

            gap_pct = (
                (
                    current_open
                    / previous_close
                )
                - 1
            ) * 100

        #
        # Close location within today's candle
        #
        # 100 = close at high
        # 0   = close at low
        #

        close_location_pct = None

        if (
            current_high is not None
            and current_low is not None
            and current_close is not None
            and current_high > current_low
        ):

            close_location_pct = (
                (
                    current_close
                    - current_low
                )
                / (
                    current_high
                    - current_low
                )
                * 100
            )

        #
        # Historical RVOL series
        #

        prior_average_series = (
            volume
            .shift(1)
            .rolling(20)
            .mean()
        )

        rvol_series = (
            volume
            / prior_average_series
        )

        rvol_3d_average = self._safe(
            rvol_series
            .tail(3)
            .mean()
        )

        high_volume_days_5d = int(
            (
                rvol_series
                .tail(5)
                >= 1.5
            )
            .sum()
        )

        #
        # Up volume / down volume
        #

        change = (
            close.diff()
        )

        recent_change = (
            change.tail(20)
        )

        recent_volume = (
            volume.tail(20)
        )

        up_volume = float(
            recent_volume[
                recent_change > 0
            ].sum()
        )

        down_volume = float(
            recent_volume[
                recent_change < 0
            ].sum()
        )

        up_down_volume_ratio = None

        if down_volume > 0:

            up_down_volume_ratio = (
                up_volume
                / down_volume
            )

        elif up_volume > 0:

            up_down_volume_ratio = 10.0

        #
        # Breakout / breakdown
        #
        # Current candle excluded from
        # reference range.
        #

        previous_20_high = self._safe(
            high.iloc[-21:-1].max()
        )

        previous_20_low = self._safe(
            low.iloc[-21:-1].min()
        )

        breakout_20d = bool(
            current_close is not None
            and previous_20_high is not None
            and current_close
            > previous_20_high
        )

        breakdown_20d = bool(
            current_close is not None
            and previous_20_low is not None
            and current_close
            < previous_20_low
        )

        #
        # OBV
        #

        obv = self._obv(
            close,
            volume,
        )

        obv_change_10d_pct = None

        if len(obv) > 10:

            old_obv = self._safe(
                obv.iloc[-11]
            )

            new_obv = self._safe(
                obv.iloc[-1]
            )

            if (
                old_obv is not None
                and new_obv is not None
            ):

                denominator = max(
                    abs(old_obv),
                    1,
                )

                obv_change_10d_pct = (
                    (
                        new_obv
                        - old_obv
                    )
                    / denominator
                    * 100
                )

        metrics = VolumeFlowMetrics(

            relative_volume=(
                self._round(
                    relative_volume,
                    3,
                )
            ),

            volume_zscore=(
                self._round(
                    volume_zscore,
                    2,
                )
            ),

            current_volume=(
                current_volume
            ),

            average_volume_20d=(
                average_volume_20d
            ),

            current_dollar_volume=(
                current_dollar_volume
            ),

            average_dollar_volume_20d=(
                average_dollar_volume_20d
            ),

            daily_change_pct=(
                self._round(
                    daily_change_pct,
                    2,
                )
            ),

            gap_pct=(
                self._round(
                    gap_pct,
                    2,
                )
            ),

            close_location_pct=(
                self._round(
                    close_location_pct,
                    1,
                )
            ),

            rvol_3d_average=(
                self._round(
                    rvol_3d_average,
                    2,
                )
            ),

            high_volume_days_5d=(
                high_volume_days_5d
            ),

            up_down_volume_ratio_20d=(
                self._round(
                    up_down_volume_ratio,
                    2,
                )
            ),

            breakout_20d=(
                breakout_20d
            ),

            breakdown_20d=(
                breakdown_20d
            ),

            obv_change_10d_pct=(
                self._round(
                    obv_change_10d_pct,
                    1,
                )
            ),
        )

        (
            metrics.flow_score,
            metrics.flow_type,
            metrics.flags,
        ) = self._score(
            metrics
        )

        return metrics

    def _score(
        self,
        m: VolumeFlowMetrics,
    ):

        score = 50.0
        flags = []

        #
        # RVOL
        #

        if m.relative_volume is not None:

            if m.relative_volume >= 10:
                score += 15

            elif m.relative_volume >= 5:
                score += 12

            elif m.relative_volume >= 3:
                score += 9

            elif m.relative_volume >= 2:
                score += 6

            elif m.relative_volume >= 1.5:
                score += 3

        #
        # Statistical abnormality
        #

        if m.volume_zscore is not None:

            if m.volume_zscore >= 5:
                score += 10
                flags.append(
                    "EXTREME_VOLUME_ZSCORE"
                )

            elif m.volume_zscore >= 3:
                score += 7

            elif m.volume_zscore >= 2:
                score += 4

        #
        # Direction of today's move
        #

        if m.daily_change_pct is not None:

            if m.daily_change_pct >= 10:
                score += 15
                flags.append(
                    "STRONG_UP_DAY"
                )

            elif m.daily_change_pct >= 5:
                score += 10

            elif m.daily_change_pct >= 2:
                score += 5

            elif m.daily_change_pct <= -10:
                score -= 20
                flags.append(
                    "STRONG_DOWN_DAY"
                )

            elif m.daily_change_pct <= -5:
                score -= 12

            elif m.daily_change_pct <= -2:
                score -= 6

        #
        # Where did it close?
        #

        if m.close_location_pct is not None:

            if m.close_location_pct >= 80:
                score += 8
                flags.append(
                    "CLOSE_NEAR_HIGH"
                )

            elif m.close_location_pct >= 65:
                score += 4

            elif m.close_location_pct <= 20:
                score -= 10
                flags.append(
                    "CLOSE_NEAR_LOW"
                )

            elif m.close_location_pct <= 35:
                score -= 5

        #
        # Up/down volume
        #

        if m.up_down_volume_ratio_20d is not None:

            if (
                m.up_down_volume_ratio_20d
                >= 2
            ):

                score += 7
                flags.append(
                    "POSITIVE_VOLUME_BALANCE"
                )

            elif (
                m.up_down_volume_ratio_20d
                <= 0.5
            ):

                score -= 7
                flags.append(
                    "NEGATIVE_VOLUME_BALANCE"
                )

        #
        # Persistence
        #

        if m.high_volume_days_5d >= 3:

            score += 5

            flags.append(
                "VOLUME_PERSISTENCE"
            )

        #
        # Breakout / breakdown
        #

        if m.breakout_20d:

            score += 10

            flags.append(
                "20D_BREAKOUT"
            )

        if m.breakdown_20d:

            score -= 15

            flags.append(
                "20D_BREAKDOWN"
            )

        score = max(
            0,
            min(
                100,
                score,
            ),
        )

        if score >= 80:

            flow_type = (
                "STRONG_ACCUMULATION"
            )

        elif score >= 65:

            flow_type = (
                "BULLISH_FLOW"
            )

        elif score <= 20:

            flow_type = (
                "STRONG_DISTRIBUTION"
            )

        elif score <= 35:

            flow_type = (
                "BEARISH_FLOW"
            )

        else:

            flow_type = "NEUTRAL"

        return (
            round(
                score,
                1,
            ),
            flow_type,
            flags,
        )

    def _obv(
        self,
        close,
        volume,
    ):

        direction = np.sign(
            close.diff()
        ).fillna(0)

        signed_volume = (
            volume
            * direction
        )

        return (
            signed_volume
            .cumsum()
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

    def _round(
        self,
        value,
        digits,
    ):

        value = self._safe(
            value
        )

        if value is None:
            return None

        return round(
            value,
            digits,
        )