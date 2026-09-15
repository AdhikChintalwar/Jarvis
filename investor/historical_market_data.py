from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import time

import pandas as pd
import yfinance as yf


@dataclass
class HistoricalPriceBundle:
    prices: pd.DataFrame
    benchmark: pd.Series | None
    source: str
    as_of: str | None
    adjusted: bool
    warnings: list[str]
    requested_period: str | None = None
    symbol_history: dict | None = None
    benchmark_history: dict | None = None


class HistoricalMarketDataProvider:
    """
    Prototype historical market-data adapter.

    Yahoo/yfinance remains secondary/prototype-grade in Baby. V4.3 explicitly
    requests auto_adjust=True so return calculations are split/dividend adjusted.
    The provider can later be replaced by a primary institutional market source
    without changing PortfolioAnalyticsEngine or BuyAndHoldBacktester.
    """

    def __init__(self, retries: int = 2, retry_delay: float = 1.0):
        self.retries = max(0, retries)
        self.retry_delay = max(0.0, retry_delay)

    def load(
        self,
        tickers: list[str],
        period: str = "5y",
        benchmark: str | None = "SPY",
    ) -> HistoricalPriceBundle:
        symbols = list(dict.fromkeys([str(x).upper() for x in tickers]))
        if benchmark:
            benchmark = benchmark.upper()
            query = list(dict.fromkeys(symbols + [benchmark]))
        else:
            query = symbols

        frame = self._download(query, period)
        if frame.empty:
            raise RuntimeError("No historical market data returned.")

        if isinstance(frame.columns, pd.MultiIndex):
            if "Close" not in frame.columns.get_level_values(0):
                raise RuntimeError("Adjusted close series unavailable.")
            close = frame["Close"].copy()
        else:
            if "Close" not in frame:
                raise RuntimeError("Adjusted close series unavailable.")
            close = frame[["Close"]].copy()
            close.columns = [query[0]]

        close = close.apply(pd.to_numeric, errors="coerce")
        prices = close[[c for c in symbols if c in close.columns]].copy()

        missing = [c for c in symbols if c not in prices.columns]
        if missing:
            raise RuntimeError(f"Missing historical series: {missing}")

        symbol_history = {}
        for symbol in symbols:
            series = prices[symbol].dropna()
            symbol_history[symbol] = self._history_meta(series)

        b = None
        benchmark_history = None
        if benchmark and benchmark in close.columns:
            b = close[benchmark].copy()
            b.name = "benchmark"
            benchmark_history = self._history_meta(b.dropna())

        as_of = None
        if len(close.dropna(how="all")):
            idx = close.dropna(how="all").index[-1]
            as_of = idx.isoformat() if hasattr(idx, "isoformat") else str(idx)

        return HistoricalPriceBundle(
            prices=prices,
            benchmark=b,
            source="Yahoo Finance via yfinance (prototype/secondary)",
            as_of=as_of,
            adjusted=True,
            warnings=[
                "Yahoo/yfinance is prototype-grade market data and is not Baby's primary truth source."
            ],
            requested_period=period,
            symbol_history=symbol_history,
            benchmark_history=benchmark_history,
        )

    @staticmethod
    def _history_meta(series):
        if series is None or len(series) == 0:
            return {
                "start": None, "end": None, "observations": 0,
                "calendar_days": 0, "calendar_years": 0.0,
            }
        start = pd.Timestamp(series.index[0])
        end = pd.Timestamp(series.index[-1])
        days = max((end - start).days, 0)
        return {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "observations": int(len(series)),
            "calendar_days": int(days),
            "calendar_years": round(days / 365.2425, 4),
        }

    def _download(self, tickers, period):
        last_error = None
        for attempt in range(self.retries + 1):
            try:
                result = yf.download(
                    tickers=tickers,
                    period=period,
                    interval="1d",
                    auto_adjust=True,
                    actions=False,
                    progress=False,
                    threads=False,
                    group_by="column",
                )
                if result is not None and not result.empty:
                    return result
            except Exception as exc:
                last_error = exc
            if attempt < self.retries:
                time.sleep(self.retry_delay * (attempt + 1))
        if last_error:
            raise RuntimeError(f"Historical market-data download failed: {last_error}")
        return pd.DataFrame()
