from __future__ import annotations

from typing import Any

import pandas as pd
import yfinance as yf

from investor.providers.base import (
    MarketDataProvider,
)


class YahooFinanceProvider(
    MarketDataProvider
):

    def _ticker(
        self,
        ticker: str,
    ):

        return yf.Ticker(
            ticker.upper()
        )

    def get_history(
        self,
        ticker: str,
        period: str = "1y",
        interval: str = "1d",
    ) -> pd.DataFrame:

        obj = self._ticker(
            ticker
        )

        data = obj.history(
            period=period,
            interval=interval,
            auto_adjust=False,
        )

        if (
            data is None
            or data.empty
        ):
            raise RuntimeError(
                f"No historical data returned "
                f"for {ticker}"
            )

        data = data.copy()

        data.columns = [
            str(column).strip()
            for column
            in data.columns
        ]

        return data

    def get_company_info(
        self,
        ticker: str,
    ) -> dict[str, Any]:

        obj = self._ticker(
            ticker
        )

        try:
            return obj.info or {}

        except Exception:
            return {}

    def get_quote(
        self,
        ticker: str,
    ) -> dict[str, Any]:

        obj = self._ticker(
            ticker
        )

        result = {}

        try:

            fast = obj.fast_info

            fields = [
                "last_price",
                "previous_close",
                "day_high",
                "day_low",
                "last_volume",
                "market_cap",
            ]

            for field in fields:

                try:
                    result[field] = getattr(
                        fast,
                        field,
                        None,
                    )

                except Exception:
                    result[field] = None

        except Exception:
            pass

        return result

    def get_news(
        self,
        ticker: str,
    ):

        obj = self._ticker(
            ticker
        )

        try:
            return obj.news or []

        except Exception:
            return []

    def get_financials(
        self,
        ticker: str,
    ):

        obj = self._ticker(
            ticker
        )

        result = {}

        try:
            result[
                "income_statement"
            ] = obj.financials

        except Exception:
            result[
                "income_statement"
            ] = None

        try:
            result[
                "balance_sheet"
            ] = obj.balance_sheet

        except Exception:
            result[
                "balance_sheet"
            ] = None

        try:
            result[
                "cash_flow"
            ] = obj.cashflow

        except Exception:
            result[
                "cash_flow"
            ] = None

        return result