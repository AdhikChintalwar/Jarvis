from __future__ import annotations
import os
from dataclasses import dataclass, asdict
import requests


@dataclass
class MacroObservation:
    series_id: str
    date: str
    value: float

    def to_dict(self):
        return asdict(self)


class FREDProvider:
    BASE = "https://api.stlouisfed.org/fred/series/observations"

    SERIES = {
        "fed_funds": "FEDFUNDS",
        "treasury_2y": "DGS2",
        "treasury_10y": "DGS10",
        "cpi": "CPIAUCSL",
        "core_cpi": "CPILFESL",
        "pce": "PCEPI",
        "core_pce": "PCEPILFE",
        "unemployment": "UNRATE",
        "payrolls": "PAYEMS",
        "real_gdp": "GDPC1",
    }

    def __init__(self, api_key: str | None = None, timeout: int = 30):
        self.api_key = api_key or os.getenv("FRED_API_KEY")
        if not self.api_key:
            raise RuntimeError(
                "Set FRED_API_KEY in .env. The official FRED series API requires an API key."
            )
        self.timeout = timeout
        self.session = requests.Session()

    def observations(self, series_id: str, limit: int = 24) -> list[MacroObservation]:
        params = {
            "series_id": series_id,
            "api_key": self.api_key,
            "file_type": "json",
            "sort_order": "desc",
            "limit": limit,
        }
        r = self.session.get(self.BASE, params=params, timeout=self.timeout)
        r.raise_for_status()
        rows = []
        for item in r.json().get("observations", []):
            if item.get("value") in (None, "."):
                continue
            try:
                value = float(item["value"])
            except ValueError:
                continue
            rows.append(MacroObservation(series_id, item["date"], value))
        rows.sort(key=lambda x: x.date)
        return rows

    def snapshot(self) -> dict[str, list[MacroObservation]]:
        return {
            name: self.observations(series_id)
            for name, series_id in self.SERIES.items()
        }
