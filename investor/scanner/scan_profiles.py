from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ScanProfile:

    name: str

    min_price: float
    max_price: float | None

    min_avg_volume: float
    min_dollar_volume: float

    min_relative_volume: float | None

    max_volatility: float | None

    min_history_days: int

    min_score: float

    weight_trend: float
    weight_momentum: float
    weight_volume: float
    weight_risk: float
    weight_setup: float

    prefer_pullback: bool = False
    prefer_breakout: bool = False
    prefer_high_rvol: bool = False
    prefer_growth: bool = False

    speculative: bool = False


PROFILES = {

    "momentum": ScanProfile(

        name="momentum",

        min_price=2,
        max_price=None,

        min_avg_volume=300_000,
        min_dollar_volume=5_000_000,

        min_relative_volume=0.70,

        max_volatility=180,

        min_history_days=80,

        min_score=58,

        weight_trend=0.30,
        weight_momentum=0.25,
        weight_volume=0.20,
        weight_risk=0.10,
        weight_setup=0.15,

        prefer_high_rvol=True,
    ),

    "breakout": ScanProfile(

        name="breakout",

        min_price=3,
        max_price=None,

        min_avg_volume=300_000,
        min_dollar_volume=8_000_000,

        min_relative_volume=1.20,

        max_volatility=150,

        min_history_days=100,

        min_score=62,

        weight_trend=0.30,
        weight_momentum=0.20,
        weight_volume=0.25,
        weight_risk=0.10,
        weight_setup=0.15,

        prefer_breakout=True,
        prefer_high_rvol=True,
    ),

    "pullback": ScanProfile(

        name="pullback",

        min_price=3,
        max_price=None,

        min_avg_volume=400_000,
        min_dollar_volume=10_000_000,

        min_relative_volume=None,

        max_volatility=120,

        min_history_days=100,

        min_score=60,

        weight_trend=0.30,
        weight_momentum=0.15,
        weight_volume=0.10,
        weight_risk=0.20,
        weight_setup=0.25,

        prefer_pullback=True,
    ),

    "unusual-volume": ScanProfile(

        name="unusual-volume",

        min_price=1,
        max_price=None,

        min_avg_volume=150_000,
        min_dollar_volume=2_000_000,

        # HARD REQUIREMENT
        min_relative_volume=1.50,

        max_volatility=250,

        min_history_days=60,

        min_score=55,

        weight_trend=0.15,
        weight_momentum=0.15,
        weight_volume=0.40,
        weight_risk=0.10,
        weight_setup=0.20,

        prefer_high_rvol=True,
    ),

    "quality": ScanProfile(

        name="quality",

        min_price=5,
        max_price=None,

        min_avg_volume=250_000,
        min_dollar_volume=15_000_000,

        min_relative_volume=None,

        max_volatility=80,

        min_history_days=180,

        min_score=62,

        weight_trend=0.25,
        weight_momentum=0.15,
        weight_volume=0.10,
        weight_risk=0.30,
        weight_setup=0.20,
    ),

    "growth": ScanProfile(

        name="growth",

        min_price=5,
        max_price=None,

        min_avg_volume=250_000,
        min_dollar_volume=10_000_000,

        min_relative_volume=None,

        max_volatility=100,

        min_history_days=120,

        min_score=60,

        weight_trend=0.30,
        weight_momentum=0.20,
        weight_volume=0.10,
        weight_risk=0.20,
        weight_setup=0.20,

        prefer_growth=True,
    ),

    "speculative": ScanProfile(

        name="speculative",

        min_price=0.50,
        max_price=30,

        min_avg_volume=300_000,
        min_dollar_volume=750_000,

        min_relative_volume=1.25,

        max_volatility=None,

        min_history_days=40,

        min_score=55,

        weight_trend=0.20,
        weight_momentum=0.20,
        weight_volume=0.30,
        weight_risk=0.05,
        weight_setup=0.25,

        speculative=True,
        prefer_high_rvol=True,
    ),
}


def get_profile(
    name: str,
) -> ScanProfile:

    normalized = (
        name
        .strip()
        .lower()
    )

    if normalized not in PROFILES:

        raise ValueError(
            f"Unknown scan profile: {name}. "
            f"Available: "
            f"{', '.join(PROFILES.keys())}"
        )

    return PROFILES[
        normalized
    ]