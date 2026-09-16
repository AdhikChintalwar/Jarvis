from __future__ import annotations

from investor.scanner.models import (
    QuantMetrics,
)

from investor.scanner.scan_profiles import (
    ScanProfile,
)


class OpportunityScorer:

    def score(
        self,
        metrics: QuantMetrics,
        profile: ScanProfile,
    ) -> QuantMetrics:

        trend = (
            self._trend_score(
                metrics
            )
        )

        momentum = (
            self._momentum_score(
                metrics
            )
        )

        volume = (
            self._volume_score(
                metrics,
                profile,
            )
        )

        risk = (
            self._risk_score(
                metrics,
                profile,
            )
        )

        setup = (
            self._setup_score(
                metrics,
                profile,
            )
        )

        overall = (

            trend
            * profile.weight_trend

            + momentum
            * profile.weight_momentum

            + volume
            * profile.weight_volume

            + risk
            * profile.weight_risk

            + setup
            * profile.weight_setup
        )

        metrics.trend_score = round(
            trend,
            1,
        )

        metrics.momentum_score = round(
            momentum,
            1,
        )

        metrics.volume_score = round(
            volume,
            1,
        )

        metrics.risk_score = round(
            risk,
            1,
        )

        metrics.setup_score = round(
            setup,
            1,
        )

        metrics.opportunity_score = round(
            overall,
            1,
        )

        metrics.scan_profile = (
            profile.name
        )

        metrics.flags.extend(
            self._flags(
                metrics
            )
        )

        metrics.flags = list(
            dict.fromkeys(
                metrics.flags
            )
        )

        return metrics

    def _trend_score(
        self,
        m,
    ):

        score = 50

        price = m.price

        if price is None:
            return 0

        if (
            m.ema_20 is not None
            and price > m.ema_20
        ):
            score += 10
        else:
            score -= 10

        if (
            m.ema_50 is not None
            and price > m.ema_50
        ):
            score += 10
        else:
            score -= 10

        if (
            m.ema_200 is not None
            and price > m.ema_200
        ):
            score += 12

        if (
            m.ema_20 is not None
            and m.ema_50 is not None
            and m.ema_20 > m.ema_50
        ):
            score += 10

        if (
            m.ema_50 is not None
            and m.ema_200 is not None
            and m.ema_50 > m.ema_200
        ):
            score += 8

        return self._clamp(
            score
        )

    def _momentum_score(
        self,
        m,
    ):

        score = 50

        if (
            m.return_20d_pct
            is not None
        ):

            if m.return_20d_pct >= 20:
                score += 20

            elif m.return_20d_pct >= 10:
                score += 12

            elif m.return_20d_pct > 0:
                score += 5

            elif m.return_20d_pct <= -15:
                score -= 18

        if (
            m.return_60d_pct
            is not None
        ):

            if m.return_60d_pct >= 30:
                score += 15

            elif m.return_60d_pct >= 10:
                score += 8

            elif m.return_60d_pct < 0:
                score -= 8

        if m.rsi_14 is not None:

            if 50 <= m.rsi_14 <= 70:
                score += 10

            elif 40 <= m.rsi_14 < 50:
                score += 3

            elif 70 < m.rsi_14 <= 80:
                score += 2

            elif m.rsi_14 > 85:
                score -= 18

            elif m.rsi_14 < 30:
                score -= 10

        return self._clamp(
            score
        )

    def _volume_score(
        self,
        m,
        profile,
    ):

        #
        # Unusual-volume scans should
        # score the CHARACTER of the flow,
        # not simply reward gigantic RVOL.
        #

        if (
            profile.name
            == "unusual-volume"
        ):

            return self._clamp(
                m.flow_score
            )

        score = 50

        rvol = (
            m.relative_volume
        )

        if rvol is None:
            return 40

        if rvol >= 5:
            score = 100

        elif rvol >= 3:
            score = 92

        elif rvol >= 2:
            score = 82

        elif rvol >= 1.5:
            score = 72

        elif rvol >= 1:
            score = 58

        elif rvol >= 0.7:
            score = 45

        else:
            score = 30

        if (
            profile.prefer_high_rvol
        ):

            if rvol >= 2:
                score += 5

            elif rvol < 0.8:
                score -= 8

        return self._clamp(
            score
        )

    def _risk_score(
        self,
        m,
        profile,
    ):

        score = 80

        volatility = (
            m.annualized_volatility
        )

        if volatility is not None:

            if volatility >= 180:
                score -= 50

            elif volatility >= 120:
                score -= 35

            elif volatility >= 80:
                score -= 22

            elif volatility >= 50:
                score -= 10

            elif volatility <= 30:
                score += 5

        drawdown = (
            m.max_drawdown_pct
        )

        if drawdown is not None:

            if drawdown >= 70:
                score -= 25

            elif drawdown >= 50:
                score -= 18

            elif drawdown >= 30:
                score -= 8

        if m.atr_pct is not None:

            if m.atr_pct >= 12:
                score -= 25

            elif m.atr_pct >= 8:
                score -= 15

            elif m.atr_pct >= 5:
                score -= 5

        if profile.speculative:
            score += 15

        return self._clamp(
            score
        )

    def _setup_score(
        self,
        m,
        profile,
    ):

        score = 50

        distance20 = (
            m.distance_ema20_pct
        )

        high_distance = (
            m.distance_52w_high_pct
        )

        if profile.prefer_pullback:

            if distance20 is not None:

                if 0 <= distance20 <= 5:
                    score += 30

                elif 5 < distance20 <= 10:
                    score += 15

                elif distance20 > 20:
                    score -= 25

                elif -4 <= distance20 < 0:
                    score += 10

        elif profile.prefer_breakout:

            if high_distance is not None:

                if -3 <= high_distance <= 0:
                    score += 30

                elif -7 <= high_distance < -3:
                    score += 18

                elif high_distance < -20:
                    score -= 15

            if m.breakout_20d:

                score += 20

            if (
                m.relative_volume
                is not None
                and m.relative_volume >= 1.5
            ):

                score += 10

        elif (
            profile.name
            == "unusual-volume"
        ):

            if m.breakout_20d:
                score += 20

            if (
                m.close_location_pct
                is not None
            ):

                if (
                    m.close_location_pct
                    >= 75
                ):
                    score += 10

                elif (
                    m.close_location_pct
                    <= 25
                ):
                    score -= 10

            if (
                m.daily_change_pct
                is not None
                and m.daily_change_pct > 0
            ):

                score += 5

        else:

            if distance20 is not None:

                if -3 <= distance20 <= 10:
                    score += 15

                elif distance20 > 20:
                    score -= 15

            if high_distance is not None:

                if high_distance >= -10:
                    score += 10

        return self._clamp(
            score
        )

    def _flags(
        self,
        m,
    ):

        flags = []

        if (
            m.relative_volume
            is not None
            and m.relative_volume >= 2
        ):

            flags.append(
                "HIGH_RVOL"
            )

        if (
            m.rsi_14 is not None
            and m.rsi_14 >= 80
        ):

            flags.append(
                "RSI_EXTENDED"
            )

        if (
            m.distance_52w_high_pct
            is not None
            and m.distance_52w_high_pct
            >= -3
        ):

            flags.append(
                "NEAR_52W_HIGH"
            )

        if (
            m.annualized_volatility
            is not None
            and m.annualized_volatility
            >= 100
        ):

            flags.append(
                "EXTREME_VOLATILITY"
            )

        if (
            m.distance_ema20_pct
            is not None
            and m.distance_ema20_pct
            >= 20
        ):

            flags.append(
                "EXTENDED_FROM_EMA20"
            )

        if (
            m.return_20d_pct
            is not None
            and m.return_20d_pct
            >= 20
        ):

            flags.append(
                "STRONG_20D_MOMENTUM"
            )

        return flags

    def _clamp(
        self,
        value,
    ):

        return max(
            0,
            min(
                100,
                float(value),
            ),
        )