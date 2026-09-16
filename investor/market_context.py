from __future__ import annotations

from dataclasses import dataclass, field

import yfinance as yf


@dataclass
class MarketAsset:
    ticker: str
    price: float | None
    change_pct: float | None


@dataclass
class MarketContext:
    regime: str
    score: float

    spy: MarketAsset
    qqq: MarketAsset
    iwm: MarketAsset

    vix: MarketAsset
    treasury_10y: MarketAsset

    observations: list[str] = field(
        default_factory=list
    )


class MarketContextEngine:

    SYMBOLS = {
        "SPY": "SPY",
        "QQQ": "QQQ",
        "IWM": "IWM",
        "VIX": "^VIX",
        "TNX": "^TNX",
    }

    def analyze(
        self,
    ) -> MarketContext:

        assets = {}

        for name, ticker in (
            self.SYMBOLS.items()
        ):

            assets[name] = (
                self._load_asset(
                    name,
                    ticker,
                )
            )

        score = 50
        observations = []

        for index_name in [
            "SPY",
            "QQQ",
            "IWM",
        ]:

            asset = assets[
                index_name
            ]

            change = asset.change_pct

            if change is None:
                continue

            if change > 1:
                score += 8

            elif change > 0:
                score += 4

            elif change < -1:
                score -= 8

            else:
                score -= 4

        vix = assets[
            "VIX"
        ].price

        if vix is not None:

            if vix >= 30:
                score -= 20

                observations.append(
                    "VIX indicates elevated market fear."
                )

            elif vix >= 20:
                score -= 8

                observations.append(
                    "Market volatility is elevated."
                )

            elif vix < 16:
                score += 6

                observations.append(
                    "Volatility conditions are relatively calm."
                )

        score = max(
            0,
            min(100, score),
        )

        if score >= 70:
            regime = "risk_on"

        elif score <= 35:
            regime = "risk_off"

        else:
            regime = "neutral"

        return MarketContext(
            regime=regime,
            score=score,

            spy=assets["SPY"],
            qqq=assets["QQQ"],
            iwm=assets["IWM"],

            vix=assets["VIX"],

            treasury_10y=(
                assets["TNX"]
            ),

            observations=observations,
        )

    def _load_asset(
        self,
        name,
        ticker,
    ):

        try:

            data = yf.Ticker(
                ticker
            ).history(
                period="5d",
                interval="1d",
                auto_adjust=False,
            )

            if (
                data is None
                or len(data) < 2
            ):
                raise ValueError()

            current = float(
                data["Close"]
                .iloc[-1]
            )

            previous = float(
                data["Close"]
                .iloc[-2]
            )

            change = (
                (
                    current
                    - previous
                )
                / previous
                * 100
            )

            return MarketAsset(
                ticker=name,
                price=current,
                change_pct=change,
            )

        except Exception:

            return MarketAsset(
                ticker=name,
                price=None,
                change_pct=None,
            )