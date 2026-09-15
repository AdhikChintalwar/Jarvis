from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any

import math
import pandas as pd
import yfinance as yf


@dataclass
class SecondaryFinancialFact:
    metric: str
    value: float | None
    period_end: str | None
    period_type: str
    source: str = "YAHOO_FINANCE"
    confidence: float = 0.72
    statement: str | None = None
    label: str | None = None

    def to_dict(self):
        return asdict(self)


class YahooAnnualFinancialAdapter:
    """
    Reads dated annual statement columns from yfinance.

    This intentionally does NOT use ticker.info TTM fields to validate SEC
    annual values.
    """

    ALIASES = {
        "revenue": (
            "Total Revenue",
            "Operating Revenue",
        ),
        "gross_profit": (
            "Gross Profit",
        ),
        "operating_income": (
            "Operating Income",
        ),
        "net_income": (
            "Net Income",
            "Net Income Common Stockholders",
        ),
        "operating_cash_flow": (
            "Operating Cash Flow",
            "Total Cash From Operating Activities",
        ),
        "capex": (
            "Capital Expenditure",
            "Capital Expenditures",
        ),
        "cash": (
            "Cash Cash Equivalents And Short Term Investments",
            "Cash And Cash Equivalents",
            "Cash",
        ),
        "short_term_investments": (
            "Other Short Term Investments",
            "Short Term Investments",
        ),
        "total_debt": (
            "Total Debt",
        ),
        "current_debt": (
            "Current Debt",
            "Current Debt And Capital Lease Obligation",
        ),
        "long_term_debt": (
            "Long Term Debt",
            "Long Term Debt And Capital Lease Obligation",
        ),
        "assets": (
            "Total Assets",
        ),
        "liabilities": (
            "Total Liabilities Net Minority Interest",
            "Total Liabilities",
        ),
        "equity": (
            "Stockholders Equity",
            "Total Equity Gross Minority Interest",
        ),
    }

    def fetch(self, ticker: str) -> dict[str, list[SecondaryFinancialFact]]:
        t = yf.Ticker(ticker.upper())

        income = self._safe_frame(lambda: t.income_stmt)
        cashflow = self._safe_frame(lambda: t.cashflow)
        balance = self._safe_frame(lambda: t.balance_sheet)

        out: dict[str, list[SecondaryFinancialFact]] = {}

        self._collect(out, income, "income_statement", (
            "revenue", "gross_profit", "operating_income", "net_income",
        ))
        self._collect(out, cashflow, "cash_flow", (
            "operating_cash_flow", "capex",
        ))
        self._collect(out, balance, "balance_sheet", (
            "cash", "short_term_investments", "total_debt",
            "current_debt", "long_term_debt",
            "assets", "liabilities", "equity",
        ))

        # Normalize Yahoo capex sign. Yahoo commonly reports capex as negative.
        for fact in out.get("capex", []):
            if fact.value is not None:
                fact.value = abs(fact.value)

        return out

    @staticmethod
    def _safe_frame(loader):
        try:
            df = loader()
            if isinstance(df, pd.DataFrame):
                return df
        except Exception:
            pass
        return pd.DataFrame()

    def _collect(self, out, df, statement, metrics):
        if df.empty:
            return

        for metric in metrics:
            row_label = self._find_row(df, self.ALIASES[metric])
            if row_label is None:
                continue

            facts = []
            row = df.loc[row_label]

            for column, raw_value in row.items():
                value = self._number(raw_value)
                if value is None:
                    continue

                period_end = self._date_string(column)
                if period_end is None:
                    continue

                facts.append(
                    SecondaryFinancialFact(
                        metric=metric,
                        value=value,
                        period_end=period_end,
                        period_type="FY",
                        statement=statement,
                        label=str(row_label),
                    )
                )

            facts.sort(
                key=lambda x: x.period_end or "",
                reverse=True,
            )

            if facts:
                out[metric] = facts

    @staticmethod
    def _find_row(df, aliases):
        index_map = {
            str(idx).strip().lower(): idx
            for idx in df.index
        }

        for alias in aliases:
            found = index_map.get(alias.lower())
            if found is not None:
                return found
        return None

    @staticmethod
    def _number(value):
        try:
            x = float(value)
        except (TypeError, ValueError):
            return None

        if math.isnan(x) or math.isinf(x):
            return None
        return x

    @staticmethod
    def _date_string(value):
        if isinstance(value, pd.Timestamp):
            return value.date().isoformat()

        if isinstance(value, datetime):
            return value.date().isoformat()

        try:
            return pd.Timestamp(value).date().isoformat()
        except Exception:
            return None
