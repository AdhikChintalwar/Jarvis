from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class TradePlan:

    setup_status: str

    current_price: float

    support_1: float | None
    support_2: float | None

    resistance_1: float | None
    resistance_2: float | None

    preferred_entry_low: float | None
    preferred_entry_high: float | None

    stop_loss: float | None

    target_1: float | None
    target_2: float | None

    risk_per_share: float | None

    reward_1: float | None
    reward_2: float | None

    risk_reward_1: float | None
    risk_reward_2: float | None

    notes: list[str]


class TradePlanEngine:

    MAX_SUPPORT_DISTANCE_PCT = 30
    MAX_RESISTANCE_DISTANCE_PCT = 50

    RECENT_DAYS = 90

    def build(
        self,
        history: pd.DataFrame,
        technical,
        risk,
        thesis,
    ) -> TradePlan:

        df = (
            history
            .copy()
            .tail(
                self.RECENT_DAYS
            )
        )

        close = (
            df["Close"]
            .astype(float)
        )

        low = (
            df["Low"]
            .astype(float)
        )

        high = (
            df["High"]
            .astype(float)
        )

        current = float(
            close.iloc[-1]
        )

        atr = (
            technical.atr_14
        )

        support_candidates = []

        #
        # Market-structure pivots
        #

        pivot_supports = (
            self._support_levels(
                low=low,
                current=current,
            )
        )

        support_candidates.extend(
            pivot_supports
        )

        #
        # Moving-average supports
        #

        for value in [
            technical.ema_20,
            technical.ema_50,
            technical.sma_20,
            technical.sma_50,
        ]:

            if (
                value is not None
                and value < current
            ):

                support_candidates.append(
                    float(value)
                )

        support_candidates = (
            self._filter_supports(
                support_candidates,
                current,
            )
        )

        resistance_candidates = (
            self._resistance_levels(
                high=high,
                current=current,
            )
        )

        resistance_candidates = (
            self._filter_resistances(
                resistance_candidates,
                current,
            )
        )

        support_1 = (
            support_candidates[0]
            if len(
                support_candidates
            ) >= 1
            else None
        )

        support_2 = (
            support_candidates[1]
            if len(
                support_candidates
            ) >= 2
            else None
        )

        resistance_1 = (
            resistance_candidates[0]
            if len(
                resistance_candidates
            ) >= 1
            else None
        )

        resistance_2 = (
            resistance_candidates[1]
            if len(
                resistance_candidates
            ) >= 2
            else None
        )

        notes = []

        entry_low = None
        entry_high = None
        stop = None

        target_1 = None
        target_2 = None

        if support_1 is not None:

            #
            # Entry zone around nearest
            # meaningful support.
            #

            entry_low = (
                support_1 * 0.985
            )

            entry_high = (
                support_1 * 1.025
            )

            #
            # Stop below structural support
            # with ATR allowance.
            #

            if atr is not None:

                stop = (
                    support_1
                    - atr * 0.85
                )

            else:

                stop = (
                    support_1
                    * 0.94
                )

        planned_entry = None

        if (
            entry_low is not None
            and entry_high is not None
        ):

            planned_entry = (
                entry_low
                + entry_high
            ) / 2

        #
        # Targets
        #

        if planned_entry is not None:

            usable_resistances = [
                value
                for value
                in resistance_candidates
                if value > planned_entry
            ]

            if usable_resistances:

                target_1 = (
                    usable_resistances[0]
                )

            if len(
                usable_resistances
            ) >= 2:

                target_2 = (
                    usable_resistances[1]
                )

            #
            # When price is already at /
            # near all-time or recent highs,
            # use ATR extension targets.
            #

            if (
                target_1 is None
                and atr is not None
            ):

                target_1 = (
                    planned_entry
                    + atr * 2
                )

            if (
                target_2 is None
                and atr is not None
            ):

                target_2 = (
                    planned_entry
                    + atr * 3
                )

        #
        # Risk / reward
        #

        risk_per_share = None

        reward_1 = None
        reward_2 = None

        rr1 = None
        rr2 = None

        if (
            planned_entry is not None
            and stop is not None
        ):

            risk_per_share = (
                planned_entry
                - stop
            )

            if risk_per_share > 0:

                if (
                    target_1 is not None
                    and target_1
                    > planned_entry
                ):

                    reward_1 = (
                        target_1
                        - planned_entry
                    )

                    rr1 = (
                        reward_1
                        / risk_per_share
                    )

                if (
                    target_2 is not None
                    and target_2
                    > planned_entry
                ):

                    reward_2 = (
                        target_2
                        - planned_entry
                    )

                    rr2 = (
                        reward_2
                        / risk_per_share
                    )

        #
        # Setup state
        #

        if thesis.decision in {
            "AVOID",
            "AVOID_OR_WATCH",
        }:

            setup_status = "AVOID"

            notes.append(
                "Underlying thesis does not "
                "currently justify a new "
                "long position."
            )

        elif (
            technical.rsi_14
            is not None
            and technical.rsi_14 >= 80
        ):

            setup_status = (
                "WAIT_FOR_PULLBACK"
            )

            notes.append(
                "RSI is extremely extended; "
                "avoid chasing current price."
            )

        elif (
            thesis.decision
            == "WAIT"
        ):

            setup_status = (
                "WAIT_FOR_CONFIRMATION"
            )

        elif support_1 is None:

            setup_status = (
                "NO_VALID_ENTRY_STRUCTURE"
            )

            notes.append(
                "No nearby technical support "
                "meets the trade-plan criteria."
            )

        else:

            setup_status = (
                "SETUP_AVAILABLE"
            )

        #
        # Additional warnings
        #

        if (
            support_1 is not None
        ):

            pullback_pct = (
                (
                    current
                    - support_1
                )
                / current
                * 100
            )

            if pullback_pct > 15:

                notes.append(
                    f"Nearest acceptable support "
                    f"requires roughly a "
                    f"{pullback_pct:.1f}% pullback."
                )

        if (
            technical
            .distance_from_ema20_pct
            is not None
            and technical
            .distance_from_ema20_pct
            > 15
        ):

            notes.append(
                "Price is substantially above "
                "its EMA20."
            )

        if (
            risk.annualized_volatility
            is not None
            and risk
            .annualized_volatility
            > 100
        ):

            notes.append(
                "Extreme volatility requires "
                "strict risk limits and "
                "smaller sizing."
            )

        if (
            rr1 is not None
            and rr1 < 1.5
        ):

            notes.append(
                "First target provides weak "
                "risk/reward."
            )

        return TradePlan(

            setup_status=(
                setup_status
            ),

            current_price=(
                self._round(
                    current
                )
            ),

            support_1=(
                self._round(
                    support_1
                )
            ),

            support_2=(
                self._round(
                    support_2
                )
            ),

            resistance_1=(
                self._round(
                    resistance_1
                )
            ),

            resistance_2=(
                self._round(
                    resistance_2
                )
            ),

            preferred_entry_low=(
                self._round(
                    entry_low
                )
            ),

            preferred_entry_high=(
                self._round(
                    entry_high
                )
            ),

            stop_loss=(
                self._round(
                    stop
                )
            ),

            target_1=(
                self._round(
                    target_1
                )
            ),

            target_2=(
                self._round(
                    target_2
                )
            ),

            risk_per_share=(
                self._round(
                    risk_per_share
                )
            ),

            reward_1=(
                self._round(
                    reward_1
                )
            ),

            reward_2=(
                self._round(
                    reward_2
                )
            ),

            risk_reward_1=(
                self._round(
                    rr1,
                    2,
                )
            ),

            risk_reward_2=(
                self._round(
                    rr2,
                    2,
                )
            ),

            notes=notes,
        )

    def _support_levels(
        self,
        low,
        current,
    ):

        candidates = []

        window = 4

        for index in range(
            window,
            len(low) - window,
        ):

            section = low.iloc[
                index - window:
                index + window + 1
            ]

            value = float(
                low.iloc[index]
            )

            if (
                value
                == section.min()
                and value < current
            ):

                candidates.append(
                    value
                )

        return candidates

    def _resistance_levels(
        self,
        high,
        current,
    ):

        candidates = []

        window = 4

        for index in range(
            window,
            len(high) - window,
        ):

            section = high.iloc[
                index - window:
                index + window + 1
            ]

            value = float(
                high.iloc[index]
            )

            if (
                value
                == section.max()
                and value > current
            ):

                candidates.append(
                    value
                )

        return candidates

    def _filter_supports(
        self,
        values,
        current,
    ):

        usable = []

        for value in values:

            if (
                value is None
                or value <= 0
                or value >= current
            ):
                continue

            distance = (
                (
                    current - value
                )
                / current
                * 100
            )

            if (
                distance
                <= self.MAX_SUPPORT_DISTANCE_PCT
            ):

                usable.append(
                    float(value)
                )

        #
        # Highest support below price
        # = closest support.
        #

        usable = sorted(
            usable,
            reverse=True,
        )

        return self._deduplicate(
            usable
        )[:5]

    def _filter_resistances(
        self,
        values,
        current,
    ):

        usable = []

        for value in values:

            if (
                value is None
                or value <= current
            ):
                continue

            distance = (
                (
                    value - current
                )
                / current
                * 100
            )

            if (
                distance
                <= self.MAX_RESISTANCE_DISTANCE_PCT
            ):

                usable.append(
                    float(value)
                )

        usable = sorted(
            usable
        )

        return self._deduplicate(
            usable
        )[:5]

    def _deduplicate(
        self,
        values,
    ):

        result = []

        for value in values:

            too_close = any(
                abs(
                    value - existing
                )
                / max(
                    existing,
                    0.01,
                )
                < 0.025

                for existing
                in result
            )

            if not too_close:

                result.append(
                    value
                )

        return result

    def _round(
        self,
        value,
        places=2,
    ):

        if value is None:
            return None

        try:

            value = float(
                value
            )

        except Exception:
            return None

        if (
            np.isnan(value)
            or np.isinf(value)
        ):
            return None

        return round(
            value,
            places,
        )