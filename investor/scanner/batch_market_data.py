from __future__ import annotations

import time
from dataclasses import dataclass

import pandas as pd
import yfinance as yf

from investor.scanner.models import (
    UniverseStock,
)


@dataclass
class BatchResult:
    data: dict[str, pd.DataFrame]
    failures: list[str]


class BatchMarketData:

    def __init__(
        self,
        batch_size: int = 100,
        pause_seconds: float = 0.6,
    ):

        self.batch_size = (
            batch_size
        )

        self.pause_seconds = (
            pause_seconds
        )

    def download(
        self,
        stocks: list[UniverseStock],
        period: str = "1y",
        interval: str = "1d",
    ) -> BatchResult:

        result = {}
        failures = []

        total = len(stocks)

        batches = [
            stocks[
                index:
                index
                + self.batch_size
            ]

            for index in range(
                0,
                total,
                self.batch_size,
            )
        ]

        for batch_index, batch in (
            enumerate(
                batches,
                start=1,
            )
        ):

            symbols = [
                stock.provider_symbol
                for stock
                in batch
            ]

            print(
                f"Market batch "
                f"{batch_index}/"
                f"{len(batches)} "
                f"({len(symbols)} symbols)"
            )

            try:

                frame = yf.download(
                    tickers=symbols,

                    period=period,
                    interval=interval,

                    auto_adjust=True,

                    group_by="ticker",

                    threads=True,

                    progress=False,
                )

                self._extract_batch(
                    frame=frame,
                    batch=batch,
                    output=result,
                    failures=failures,
                )

            except Exception as error:

                print(
                    "Batch warning:",
                    error,
                )

                failures.extend(
                    stock.symbol
                    for stock
                    in batch
                )

            if (
                batch_index
                < len(batches)
            ):

                time.sleep(
                    self.pause_seconds
                )

        return BatchResult(
            data=result,
            failures=failures,
        )

    def _extract_batch(
        self,
        frame,
        batch,
        output,
        failures,
    ):

        if frame is None:
            return

        for stock in batch:

            symbol = (
                stock.provider_symbol
            )

            try:

                data = self._extract_symbol(
                    frame,
                    symbol,
                    single=(
                        len(batch) == 1
                    ),
                )

                if (
                    data is None
                    or data.empty
                ):

                    failures.append(
                        stock.symbol
                    )

                    continue

                required = {
                    "Open",
                    "High",
                    "Low",
                    "Close",
                    "Volume",
                }

                if not required.issubset(
                    set(data.columns)
                ):

                    failures.append(
                        stock.symbol
                    )

                    continue

                data = data[
                    list(required)
                ].copy()

                data = (
                    data
                    .dropna(
                        subset=[
                            "Close"
                        ]
                    )
                )

                if data.empty:

                    failures.append(
                        stock.symbol
                    )

                    continue

                output[
                    stock.symbol
                ] = data

            except Exception:

                failures.append(
                    stock.symbol
                )

    def _extract_symbol(
        self,
        frame,
        symbol,
        single,
    ):

        if single:

            if (
                isinstance(
                    frame.columns,
                    pd.MultiIndex,
                )
            ):

                if symbol in (
                    frame.columns
                    .get_level_values(0)
                ):

                    return frame[
                        symbol
                    ].copy()

            return frame.copy()

        if not isinstance(
            frame.columns,
            pd.MultiIndex,
        ):

            return None

        top = (
            frame.columns
            .get_level_values(0)
        )

        if symbol in top:

            return frame[
                symbol
            ].copy()

        # yfinance versions occasionally
        # return Price/Ticker instead of
        # Ticker/Price.

        second = (
            frame.columns
            .get_level_values(1)
        )

        if symbol in second:

            return (
                frame.xs(
                    symbol,
                    level=1,
                    axis=1,
                )
                .copy()
            )

        return None