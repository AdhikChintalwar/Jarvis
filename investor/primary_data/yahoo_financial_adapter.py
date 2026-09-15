from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class YahooFinancialAdapter:
    """
    Adapter only. Yahoo/yfinance remains secondary/prototype-grade.

    Accepts the dictionary returned by the existing Yahoo provider's
    company-info / fundamentals layer and maps common fields into Baby's
    normalized vocabulary.
    """

    FIELD_MAP = {
        "revenue": (
            "totalRevenue",
            "revenue",
        ),
        "revenue_growth_yoy": (
            "revenueGrowth",
            "revenue_growth",
        ),
        "gross_margin": (
            "grossMargins",
            "gross_margin",
        ),
        "operating_margin": (
            "operatingMargins",
            "operating_margin",
        ),
        "net_margin": (
            "profitMargins",
            "profit_margin",
            "net_margin",
        ),
        "operating_cash_flow": (
            "operatingCashflow",
            "operating_cash_flow",
        ),
        "free_cash_flow": (
            "freeCashflow",
            "free_cash_flow",
        ),
        "cash": (
            "totalCash",
            "cash",
        ),
        "debt": (
            "totalDebt",
            "debt",
        ),
        "shares_outstanding": (
            "sharesOutstanding",
            "shares_outstanding",
        ),
    }

    def normalize(self, info: dict[str, Any]) -> dict:
        output = {}

        for normalized, aliases in self.FIELD_MAP.items():
            value = None
            for alias in aliases:
                if alias in info and info[alias] is not None:
                    value = info[alias]
                    break
            output[normalized] = value

        return output
