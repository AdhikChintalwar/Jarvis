from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import pandas as pd


class MarketDataProvider(ABC):

    @abstractmethod
    def get_history(
        self,
        ticker: str,
        period: str = "1y",
        interval: str = "1d",
    ) -> pd.DataFrame:
        raise NotImplementedError

    @abstractmethod
    def get_company_info(
        self,
        ticker: str,
    ) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def get_quote(
        self,
        ticker: str,
    ) -> dict[str, Any]:
        raise NotImplementedError