from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class VolumeEvent:
    date: str
    volume: float
    relative_volume: float
    price_change_pct: float
    dollar_volume: float
    direction: str


@dataclass
class AbnormalVolumeAnalysis:
    current_relative_volume: float | None

    average_relative_volume_5d: float | None

    abnormal_days_20d: int

    extreme_volume_days_20d: int

    bullish_volume_events: int

    bearish_volume_events: int

    accumulation_score: float

    volume_signal: str

    events: list[VolumeEvent] = field(
        default_factory=list
    )


class AbnormalVolumeEngine:

    def analyze(
        self,
        history: pd.DataFrame,
    ) -> AbnormalVolumeAnalysis:

        df = history.copy()

        close = df["Close"].astype(float)
        volume = df["Volume"].astype(float)

        average_volume = (
            volume.shift(1)
            .rolling(20)
            .mean()
        )

        relative_volume = (
            volume
            / average_volume.replace(
                0,
                np.nan,
            )
        )

        returns = (
            close.pct_change() * 100
        )

        dollar_volume = (
            close * volume
        )

        recent = df.tail(20)

        recent_indexes = (
            recent.index
        )

        events = []

        abnormal_days = 0
        extreme_days = 0

        bullish_events = 0
        bearish_events = 0

        for index in recent_indexes:

            rv = (
                relative_volume.loc[
                    index
                ]
            )

            change = (
                returns.loc[
                    index
                ]
            )

            if (
                pd.isna(rv)
                or pd.isna(change)
            ):
                continue

            if rv >= 1.5:

                abnormal_days += 1

                if rv >= 3:
                    extreme_days += 1

                direction = (
                    "bullish"
                    if change > 0
                    else "bearish"
                )

                if direction == "bullish":
                    bullish_events += 1
                else:
                    bearish_events += 1

                events.append(
                    VolumeEvent(
                        date=str(
                            index.date()
                        ),

                        volume=float(
                            volume.loc[index]
                        ),

                        relative_volume=float(
                            rv
                        ),

                        price_change_pct=float(
                            change
                        ),

                        dollar_volume=float(
                            dollar_volume.loc[
                                index
                            ]
                        ),

                        direction=direction,
                    )
                )

        current_rvol = None

        if not relative_volume.empty:

            latest = (
                relative_volume.iloc[-1]
            )

            if not pd.isna(latest):
                current_rvol = float(
                    latest
                )

        avg_5 = (
            relative_volume
            .tail(5)
            .mean()
        )

        avg_5 = (
            None
            if pd.isna(avg_5)
            else float(avg_5)
        )

        score = 50

        score += (
            bullish_events * 8
        )

        score -= (
            bearish_events * 8
        )

        score += min(
            extreme_days * 5,
            15,
        )

        score = max(
            0,
            min(100, score),
        )

        if score >= 70:
            signal = "accumulation"

        elif score <= 30:
            signal = "distribution"

        else:
            signal = "neutral"

        return AbnormalVolumeAnalysis(
            current_relative_volume=(
                current_rvol
            ),

            average_relative_volume_5d=(
                avg_5
            ),

            abnormal_days_20d=(
                abnormal_days
            ),

            extreme_volume_days_20d=(
                extreme_days
            ),

            bullish_volume_events=(
                bullish_events
            ),

            bearish_volume_events=(
                bearish_events
            ),

            accumulation_score=round(
                score,
                1,
            ),

            volume_signal=signal,

            events=events[
                -10:
            ],
        )