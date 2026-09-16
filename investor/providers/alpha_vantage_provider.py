from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import hashlib
import json
import math
import os
import time

import pandas as pd
import requests
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(dotenv_path=PROJECT_ROOT / ".env", override=False)


class AlphaVantageError(RuntimeError):
    pass


@dataclass
class ExternalReferencePacket:
    symbol: str
    source: str = "Alpha Vantage"
    provider: str = "ALPHA_VANTAGE"
    independent: bool = True
    authority: str = "INDEPENDENT_SECONDARY"
    status: str = "ACTIVE"
    as_of: str | None = None
    financial_as_of: str | None = None
    market_as_of: str | None = None

    current_price: float | None = None
    sma_20: float | None = None
    sma_50: float | None = None
    ema_20: float | None = None
    rsi_14: float | None = None

    revenue: float | None = None
    net_income: float | None = None
    operating_cash_flow: float | None = None
    capital_expenditures: float | None = None
    free_cash_flow: float | None = None
    cash: float | None = None
    debt: float | None = None

    warnings: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["warnings"] = list(self.warnings or [])
        return d


class AlphaVantageProvider:
    """Independent, read-only validation provider.

    It never overwrites Baby's SEC/XBRL primary facts. The compact daily endpoint
    supplies enough observations for 20/50-day indicator reconciliation. Financial
    comparisons use the latest annual Alpha Vantage statements.

    Responses are cached on disk to protect low API quotas. API keys are loaded
    only from the local environment and are never written to cache.
    """

    BASE_URL = "https://www.alphavantage.co/query"

    def __init__(
        self,
        api_key: str | None = None,
        cache_dir: str | Path | None = None,
        market_ttl_seconds: int = 6 * 60 * 60,
        fundamental_ttl_seconds: int = 7 * 24 * 60 * 60,
        timeout_seconds: int = 20,
        min_request_interval_seconds: float = 1.25,
        max_retries: int = 3,
        session: requests.Session | None = None,
        sleep_fn=time.sleep,
    ):
        self.api_key = (
            api_key
            or os.getenv("ALPHA_VANTAGE_API_KEY")
            or os.getenv("ALPHAVANTAGE_API_KEY")
        )
        self.cache_dir = Path(cache_dir or PROJECT_ROOT / "data" / "provider_cache" / "alpha_vantage")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.market_ttl_seconds = int(market_ttl_seconds)
        self.fundamental_ttl_seconds = int(fundamental_ttl_seconds)
        self.timeout_seconds = int(timeout_seconds)
        self.min_request_interval_seconds = float(min_request_interval_seconds)
        self.max_retries = int(max_retries)
        self.session = session or requests.Session()
        self.sleep_fn = sleep_fn
        self._last_network_request_at = 0.0

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def build_reference(self, symbol: str) -> dict[str, Any]:
        symbol = str(symbol).strip().upper()
        if not symbol:
            raise ValueError("symbol is required")
        if not self.configured:
            return ExternalReferencePacket(
                symbol=symbol,
                status="UNCONFIGURED",
                warnings=["ALPHA_VANTAGE_API_KEY is not configured."],
            ).to_dict()

        warnings: list[str] = []
        daily = income = balance = cashflow = None

        for fn, bucket in (
            ("TIME_SERIES_DAILY", "market"),
            ("INCOME_STATEMENT", "fundamental"),
            ("BALANCE_SHEET", "fundamental"),
            ("CASH_FLOW", "fundamental"),
        ):
            try:
                payload = self._query(fn, symbol, bucket)
            except Exception as exc:
                warnings.append(f"{fn}: {type(exc).__name__}: {exc}")
                payload = None
            if fn == "TIME_SERIES_DAILY":
                daily = payload
            elif fn == "INCOME_STATEMENT":
                income = payload
            elif fn == "BALANCE_SHEET":
                balance = payload
            elif fn == "CASH_FLOW":
                cashflow = payload

        market = self._market_metrics(daily)
        fin = self._financial_metrics(income, balance, cashflow)

        available = sum(v is not None for v in {**market, **fin}.values())
        status = "ACTIVE" if available else "UNAVAILABLE"
        as_of = max(
            [x for x in (market.get("market_as_of"), fin.get("financial_as_of")) if x],
            default=None,
        )
        packet = ExternalReferencePacket(
            symbol=symbol,
            status=status,
            as_of=as_of,
            market_as_of=market.pop("market_as_of", None),
            financial_as_of=fin.pop("financial_as_of", None),
            warnings=warnings,
            **market,
            **fin,
        )
        return packet.to_dict()

    def _query(self, function: str, symbol: str, bucket: str) -> dict[str, Any]:
        ttl = self.market_ttl_seconds if bucket == "market" else self.fundamental_ttl_seconds
        cache = self._cache_path(function, symbol)
        cached = self._read_cache(cache, ttl)
        if cached is not None:
            return cached

        params = {"function": function, "symbol": symbol, "apikey": self.api_key}
        if function == "TIME_SERIES_DAILY":
            params["outputsize"] = "compact"

        last_error = None
        for attempt in range(self.max_retries):
            elapsed = time.monotonic() - self._last_network_request_at
            wait = self.min_request_interval_seconds - elapsed
            if wait > 0:
                self.sleep_fn(wait)
            try:
                response = self.session.get(self.BASE_URL, params=params, timeout=self.timeout_seconds)
                self._last_network_request_at = time.monotonic()
                response.raise_for_status()
                data = response.json()
                if not isinstance(data, dict):
                    raise AlphaVantageError("Provider returned a non-object JSON response.")
                message = data.get("Error Message") or data.get("Note") or data.get("Information")
                if message:
                    text = str(message)
                    rate_limited = any(x in text.lower() for x in ("rate", "frequency", "requests per", "spread", "premium"))
                    if rate_limited and attempt + 1 < self.max_retries:
                        self.sleep_fn(max(self.min_request_interval_seconds, 2.0 * (attempt + 1)))
                        last_error = AlphaVantageError(text)
                        continue
                    raise AlphaVantageError(text)
                self._write_cache(cache, data)
                return data
            except (requests.RequestException, ValueError, AlphaVantageError) as exc:
                last_error = exc
                if attempt + 1 < self.max_retries:
                    self.sleep_fn(max(self.min_request_interval_seconds, 2.0 ** attempt))
                    continue
        stale = self._read_cache(cache, None)
        if stale is not None:
            return stale
        raise AlphaVantageError(str(last_error or "Alpha Vantage request failed."))

    def _market_metrics(self, payload: dict[str, Any] | None) -> dict[str, Any]:
        out = {
            "current_price": None, "sma_20": None, "sma_50": None,
            "ema_20": None, "rsi_14": None, "market_as_of": None,
        }
        if not payload:
            return out
        series = payload.get("Time Series (Daily)")
        if not isinstance(series, dict) or not series:
            return out

        rows = []
        for date, row in series.items():
            if not isinstance(row, dict):
                continue
            close = self._num(row.get("4. close"))
            if close is not None:
                rows.append((str(date), close))
        rows.sort(key=lambda x: x[0])
        if not rows:
            return out

        dates = [x[0] for x in rows]
        close = pd.Series([x[1] for x in rows], dtype=float)
        out["market_as_of"] = dates[-1]
        out["current_price"] = float(close.iloc[-1])
        if len(close) >= 20:
            out["sma_20"] = float(close.tail(20).mean())
            out["ema_20"] = float(close.ewm(span=20, adjust=False).mean().iloc[-1])
        if len(close) >= 50:
            out["sma_50"] = float(close.tail(50).mean())
        if len(close) >= 15:
            delta = close.diff()
            gain = delta.clip(lower=0)
            loss = -delta.clip(upper=0)
            avg_gain = gain.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
            avg_loss = loss.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
            ag, al = avg_gain.iloc[-1], avg_loss.iloc[-1]
            if pd.notna(ag) and pd.notna(al):
                out["rsi_14"] = 100.0 if al == 0 and ag > 0 else 50.0 if al == 0 else float(100 - 100/(1 + ag/al))
        return out

    def _financial_metrics(
        self,
        income: dict[str, Any] | None,
        balance: dict[str, Any] | None,
        cashflow: dict[str, Any] | None,
    ) -> dict[str, Any]:
        out = {
            "revenue": None, "net_income": None, "operating_cash_flow": None,
            "capital_expenditures": None, "free_cash_flow": None,
            "cash": None, "debt": None, "financial_as_of": None,
        }
        inc = self._latest_annual(income)
        bal = self._latest_annual(balance)
        cf = self._latest_annual(cashflow)

        out["revenue"] = self._num(inc.get("totalRevenue"))
        out["net_income"] = self._num(inc.get("netIncome"))
        out["operating_cash_flow"] = self._num(cf.get("operatingCashflow"))
        capex = self._num(cf.get("capitalExpenditures"))
        out["capital_expenditures"] = abs(capex) if capex is not None else None
        if out["operating_cash_flow"] is not None and out["capital_expenditures"] is not None:
            out["free_cash_flow"] = out["operating_cash_flow"] - out["capital_expenditures"]

        out["cash"] = self._first_num(
            bal,
            "cashAndCashEquivalentsAtCarryingValue",
            "cashAndShortTermInvestments",
        )
        total_debt = self._num(bal.get("shortLongTermDebtTotal"))
        if total_debt is None:
            current = self._first_num(bal, "currentDebt", "shortTermDebt")
            longterm = self._first_num(bal, "longTermDebt", "longTermDebtNoncurrent")
            if current is not None or longterm is not None:
                total_debt = float(current or 0.0) + float(longterm or 0.0)
        out["debt"] = total_debt

        dates = [
            str(x.get("fiscalDateEnding"))
            for x in (inc, bal, cf)
            if x and x.get("fiscalDateEnding")
        ]
        out["financial_as_of"] = max(dates, default=None)
        return out

    @staticmethod
    def _latest_annual(payload: dict[str, Any] | None) -> dict[str, Any]:
        if not payload:
            return {}
        reports = payload.get("annualReports")
        if not isinstance(reports, list) or not reports:
            return {}
        valid = [x for x in reports if isinstance(x, dict)]
        return max(valid, key=lambda x: str(x.get("fiscalDateEnding") or ""), default={})

    @staticmethod
    def _num(v: Any) -> float | None:
        if v is None or isinstance(v, bool):
            return None
        try:
            x = float(v)
            return x if math.isfinite(x) else None
        except (TypeError, ValueError):
            return None

    @classmethod
    def _first_num(cls, d: dict[str, Any], *keys: str) -> float | None:
        for k in keys:
            x = cls._num(d.get(k))
            if x is not None:
                return x
        return None

    def _cache_path(self, function: str, symbol: str) -> Path:
        safe = hashlib.sha256(f"{function}:{symbol}".encode()).hexdigest()[:16]
        return self.cache_dir / f"{symbol}_{function}_{safe}.json"

    @staticmethod
    def _read_cache(path: Path, ttl: int | None) -> dict[str, Any] | None:
        if not path.exists():
            return None
        if ttl is not None and time.time() - path.stat().st_mtime > ttl:
            return None
        try:
            body = json.loads(path.read_text())
            return body if isinstance(body, dict) else None
        except Exception:
            return None

    @staticmethod
    def _write_cache(path: Path, data: dict[str, Any]) -> None:
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data))
        tmp.replace(path)
