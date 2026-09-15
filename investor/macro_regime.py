from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
import copy
import os
import threading
import time
import requests
import yfinance as yf

try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None


@dataclass
class MacroObservation:
    name: str
    value: float | None = None
    change_1d_pct: float | None = None
    change_20d_pct: float | None = None
    trend: str = "unknown"
    as_of: str | None = None
    source: str = ""
    authority: float = 0.0
    unit: str | None = None
    metadata: dict = field(default_factory=dict)


@dataclass
class MacroRegimeReport:
    regime: str = "UNKNOWN"
    score: float = 50.0
    confidence: float = 0.0
    coverage: float = 0.0

    financial_conditions: str = "unknown"
    volatility_regime: str = "unknown"
    equity_regime: str = "unknown"
    rate_regime: str = "unknown"

    inflation_regime: str = "unknown"
    labor_regime: str = "unknown"
    fed_policy_state: str = "unknown"
    yield_curve_state: str = "unknown"

    cpi_yoy_pct: float | None = None
    cpi_mom_pct: float | None = None
    unemployment_rate: float | None = None
    unemployment_change_3m_pp: float | None = None
    fed_funds_rate: float | None = None
    treasury_2y: float | None = None
    treasury_10y: float | None = None
    yield_curve_2s10s_bp: float | None = None

    observations: dict = field(default_factory=dict)
    positives: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    unknowns: list[str] = field(default_factory=list)

    generated_at: str = ""
    cache_age_seconds: float = 0.0
    schema_version: str = "4.0.1"


class MacroRegimeEngine:
    """
    Deterministic macro/regime engine.

    Primary macro facts:
      FRED DFF       effective federal funds rate
      FRED CPIAUCSL  CPI index, transformed here into YoY/MoM inflation
      FRED UNRATE    unemployment rate
      FRED DGS2      2-year Treasury constant maturity
      FRED DGS10     10-year Treasury constant maturity

    Secondary market proxies:
      Yahoo SPY / QQQ / IWM / ^VIX

    Missing observations are neutral. They never create bearish pressure.
    """

    MARKET_SYMBOLS = {
        "SPY": "SPY",
        "QQQ": "QQQ",
        "IWM": "IWM",
        "VIX": "^VIX",
    }

    FRED_SERIES = {
        "fed_funds": "DFF",
        "cpi": "CPIAUCSL",
        "unemployment": "UNRATE",
        "treasury_2y": "DGS2",
        "treasury_10y": "DGS10",
    }

    _cache_lock = threading.Lock()
    _cached_report: MacroRegimeReport | None = None
    _cached_at_monotonic: float | None = None

    def __init__(self, cache_ttl_seconds: int = 1800):
        root = Path(__file__).resolve().parents[1]
        if load_dotenv:
            load_dotenv(dotenv_path=root / ".env", override=False)

        self.fred_key = os.getenv("FRED_API_KEY", "").strip()
        self.cache_ttl_seconds = max(0, int(cache_ttl_seconds))

    @classmethod
    def clear_cache(cls):
        with cls._cache_lock:
            cls._cached_report = None
            cls._cached_at_monotonic = None

    def analyze(self, force_refresh: bool = False) -> MacroRegimeReport:
        if not force_refresh:
            cached = self._get_cached()
            if cached is not None:
                return cached

        report = self._build_report()
        self._set_cached(report)
        return copy.deepcopy(report)

    def _get_cached(self):
        cls = type(self)
        with cls._cache_lock:
            if cls._cached_report is None or cls._cached_at_monotonic is None:
                return None

            age = time.monotonic() - cls._cached_at_monotonic
            if age > self.cache_ttl_seconds:
                return None

            result = copy.deepcopy(cls._cached_report)
            result.cache_age_seconds = round(age, 2)
            return result

    def _set_cached(self, report):
        cls = type(self)
        with cls._cache_lock:
            cls._cached_report = copy.deepcopy(report)
            cls._cached_at_monotonic = time.monotonic()

    def _build_report(self):
        obs = {}

        for name, symbol in self.MARKET_SYMBOLS.items():
            obs[name] = self._market_observation(name, symbol)

        fred_history = {}
        for name, series in self.FRED_SERIES.items():
            if self.fred_key:
                history = self._fred_history(series, limit=self._fred_limit(name))
                fred_history[name] = history
                obs[name] = self._fred_observation(name, series, history)
            else:
                fred_history[name] = []
                obs[name] = MacroObservation(
                    name=name,
                    source=f"FRED:{series}",
                    authority=0.0,
                )

        positives = []
        risks = []
        unknowns = []
        score = 50.0

        def pressure(points, authority, text):
            nonlocal score
            if authority <= 0:
                return
            score += points * authority
            (positives if points > 0 else risks).append(text)

        # ---------------- Equity breadth ----------------
        equity = [
            obs[k]
            for k in ("SPY", "QQQ", "IWM")
            if obs[k].change_20d_pct is not None
        ]

        bullish = sum(x.change_20d_pct > 2 for x in equity)
        bearish = sum(x.change_20d_pct < -2 for x in equity)

        if len(equity) >= 2:
            if bullish >= 2:
                equity_regime = "bullish"
                pressure(12, 0.70, "Broad equity trend is supportive.")
            elif bearish >= 2:
                equity_regime = "bearish"
                pressure(-12, 0.70, "Broad equity trend is weak.")
            else:
                equity_regime = "mixed"
        else:
            equity_regime = "unknown"
            unknowns.append("equity_trend")

        # ---------------- Volatility ----------------
        vix = obs["VIX"]
        if vix.value is None:
            volatility = "unknown"
            unknowns.append("vix")
        elif vix.value >= 30:
            volatility = "high_stress"
            pressure(-18, vix.authority, "VIX indicates high market stress.")
        elif vix.value >= 22:
            volatility = "elevated"
            pressure(-9, vix.authority, "VIX is elevated.")
        elif vix.value < 16:
            volatility = "calm"
            pressure(6, vix.authority, "VIX is relatively calm.")
        else:
            volatility = "normal"

        # ---------------- Treasury rates + yield curve ----------------
        y2 = obs["treasury_2y"]
        y10 = obs["treasury_10y"]

        treasury_2y = y2.value
        treasury_10y = y10.value

        if treasury_10y is None:
            rate_regime = "unknown"
            unknowns.append("fred_treasury_10y")
        else:
            rate_change_bp = y10.metadata.get("change_20obs_bp")
            if rate_change_bp is None:
                rate_regime = "level_only"
            elif rate_change_bp >= 20:
                rate_regime = "rising"
                pressure(-7, y10.authority, "10-year Treasury yield is rising.")
            elif rate_change_bp <= -20:
                rate_regime = "falling"
                pressure(5, y10.authority, "10-year Treasury yield is falling.")
            else:
                rate_regime = "stable"

        if treasury_2y is not None and treasury_10y is not None:
            spread_bp = (treasury_10y - treasury_2y) * 100.0
            if spread_bp < -25:
                yield_curve_state = "inverted"
                pressure(-5, min(y2.authority, y10.authority),
                         "2Y/10Y Treasury curve is inverted.")
            elif spread_bp <= 25:
                yield_curve_state = "flat"
            else:
                yield_curve_state = "normal"
        else:
            spread_bp = None
            yield_curve_state = "unknown"
            unknowns.append("yield_curve_2s10s")

        # ---------------- Inflation semantics ----------------
        cpi_history = fred_history.get("cpi", [])
        cpi_yoy, cpi_mom, inflation_trend_delta = self._cpi_metrics(cpi_history)

        if cpi_yoy is None:
            inflation_regime = "unknown"
            unknowns.append("cpi_inflation")
        else:
            if inflation_trend_delta is None:
                inflation_regime = "available"
            elif inflation_trend_delta >= 0.20:
                inflation_regime = "accelerating"
                pressure(-6, obs["cpi"].authority,
                         "Year-over-year CPI inflation is accelerating.")
            elif inflation_trend_delta <= -0.20:
                inflation_regime = "cooling"
                pressure(5, obs["cpi"].authority,
                         "Year-over-year CPI inflation is cooling.")
            else:
                inflation_regime = "stable"

            if cpi_yoy >= 4.0:
                pressure(-5, obs["cpi"].authority,
                         "Year-over-year CPI inflation remains elevated.")

        # ---------------- Labor semantics ----------------
        unemployment_history = fred_history.get("unemployment", [])
        unemployment_rate, unemployment_change_3m_pp = self._unemployment_metrics(
            unemployment_history
        )

        if unemployment_rate is None:
            labor_regime = "unknown"
            unknowns.append("fred_unemployment")
        elif unemployment_change_3m_pp is None:
            labor_regime = "available"
        elif unemployment_change_3m_pp >= 0.30:
            labor_regime = "weakening"
            pressure(-5, obs["unemployment"].authority,
                     "Unemployment has risen materially over the last three observations.")
        elif unemployment_change_3m_pp <= -0.30:
            labor_regime = "improving"
            pressure(3, obs["unemployment"].authority,
                     "Unemployment has declined over the last three observations.")
        else:
            labor_regime = "stable"

        # ---------------- Fed policy ----------------
        fed = obs["fed_funds"]
        fed_rate = fed.value

        if fed_rate is None:
            fed_state = "unknown"
            unknowns.append("fred_fed_funds")
        elif fed_rate >= 4.0:
            fed_state = "restrictive"
        elif fed_rate <= 2.0:
            fed_state = "accommodative"
        else:
            fed_state = "intermediate"

        # This is deliberately descriptive rather than a claim about the
        # theoretical neutral rate.
        fed_change_bp = fed.metadata.get("change_20obs_bp")
        if fed_change_bp is not None:
            if fed_change_bp <= -20:
                positives.append("Effective federal funds rate has been declining.")
            elif fed_change_bp >= 20:
                risks.append("Effective federal funds rate has been rising.")

        # ---------------- Financial conditions synthesis ----------------
        if (
            volatility in {"high_stress", "elevated"}
            and rate_regime == "rising"
        ):
            conditions = "tightening"
        elif (
            volatility == "calm"
            and rate_regime == "falling"
        ):
            conditions = "easing"
        else:
            conditions = "mixed"

        score = max(0.0, min(100.0, score))

        if score >= 65:
            regime = "RISK_ON"
        elif score <= 35:
            regime = "RISK_OFF"
        elif (
            equity_regime == "bearish"
            and volatility in {"elevated", "high_stress"}
        ):
            regime = "RISK_OFF"
        else:
            regime = "NEUTRAL"

        desired = (
            "SPY", "QQQ", "IWM", "VIX",
            "fed_funds", "cpi", "unemployment",
            "treasury_2y", "treasury_10y",
        )
        available = [obs[k] for k in desired if obs[k].value is not None]
        coverage = len(available) / len(desired) * 100.0
        confidence = (
            sum(x.authority for x in available) / len(available) * 100.0
            if available else 0.0
        )

        return MacroRegimeReport(
            regime=regime,
            score=round(score, 2),
            confidence=round(confidence, 2),
            coverage=round(coverage, 2),
            financial_conditions=conditions,
            volatility_regime=volatility,
            equity_regime=equity_regime,
            rate_regime=rate_regime,
            inflation_regime=inflation_regime,
            labor_regime=labor_regime,
            fed_policy_state=fed_state,
            yield_curve_state=yield_curve_state,
            cpi_yoy_pct=self._round(cpi_yoy),
            cpi_mom_pct=self._round(cpi_mom),
            unemployment_rate=self._round(unemployment_rate),
            unemployment_change_3m_pp=self._round(unemployment_change_3m_pp),
            fed_funds_rate=self._round(fed_rate),
            treasury_2y=self._round(treasury_2y),
            treasury_10y=self._round(treasury_10y),
            yield_curve_2s10s_bp=self._round(spread_bp),
            observations={k: asdict(v) for k, v in obs.items()},
            positives=positives,
            risks=risks,
            unknowns=unknowns,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

    def _market_observation(self, name, symbol):
        try:
            data = yf.Ticker(symbol).history(
                period="3mo",
                interval="1d",
                auto_adjust=False,
            )

            if data is None or len(data) < 2:
                raise ValueError("insufficient history")

            close = data["Close"].dropna()
            if len(close) < 2:
                raise ValueError("insufficient close history")

            current = float(close.iloc[-1])
            previous = float(close.iloc[-2])

            one = (current / previous - 1) * 100.0
            twenty = (
                (current / float(close.iloc[-21]) - 1) * 100.0
                if len(close) >= 21
                else None
            )

            idx = close.index[-1]
            as_of = idx.isoformat() if hasattr(idx, "isoformat") else str(idx)

            trend = "unknown"
            if twenty is not None:
                trend = (
                    "rising" if twenty > 2
                    else "falling" if twenty < -2
                    else "flat"
                )

            return MacroObservation(
                name=name,
                value=current,
                change_1d_pct=round(one, 4),
                change_20d_pct=round(twenty, 4) if twenty is not None else None,
                trend=trend,
                as_of=as_of,
                source="Yahoo market proxy",
                authority=0.70,
                metadata={"symbol": symbol},
            )

        except Exception as error:
            return MacroObservation(
                name=name,
                source="Yahoo market proxy",
                authority=0.0,
                metadata={"symbol": symbol, "error": type(error).__name__},
            )

    def _fred_limit(self, name):
        if name == "cpi":
            return 30
        if name == "unemployment":
            return 12
        return 45

    def _fred_history(self, series, limit=30):
        try:
            response = requests.get(
                "https://api.stlouisfed.org/fred/series/observations",
                params={
                    "series_id": series,
                    "api_key": self.fred_key,
                    "file_type": "json",
                    "sort_order": "desc",
                    "limit": limit,
                },
                timeout=15,
            )
            response.raise_for_status()

            values = []
            for item in response.json().get("observations", []):
                try:
                    values.append((item["date"], float(item["value"])))
                except (TypeError, ValueError, KeyError):
                    continue

            return values

        except Exception:
            return []

    def _fred_observation(self, name, series, history):
        if not history:
            return MacroObservation(
                name=name,
                source=f"FRED:{series}",
                authority=0.0,
            )

        current_date, current_value = history[0]

        metadata = {"series_id": series}
        trend = "unknown"

        if name in {"fed_funds", "treasury_2y", "treasury_10y"}:
            if len(history) >= 21:
                old_value = history[20][1]
                change_bp = (current_value - old_value) * 100.0
                metadata["change_20obs_bp"] = round(change_bp, 2)
                trend = (
                    "rising" if change_bp >= 20
                    else "falling" if change_bp <= -20
                    else "flat"
                )

        return MacroObservation(
            name=name,
            value=current_value,
            trend=trend,
            as_of=current_date,
            source=f"FRED:{series}",
            authority=0.98,
            unit="percent" if name != "cpi" else "index",
            metadata=metadata,
        )

    @staticmethod
    def _cpi_metrics(history):
        # FRED history is newest first. CPIAUCSL is monthly.
        # YoY = latest / 12-month-prior - 1
        # MoM = latest / previous-month - 1
        # trend delta = current YoY - YoY three months earlier.
        if len(history) < 13:
            return None, None, None

        latest = history[0][1]
        previous = history[1][1]
        year_ago = history[12][1]

        mom = (latest / previous - 1) * 100.0 if previous else None
        yoy = (latest / year_ago - 1) * 100.0 if year_ago else None

        trend_delta = None
        if len(history) >= 16:
            old_latest = history[3][1]
            old_year_ago = history[15][1]
            old_yoy = (
                (old_latest / old_year_ago - 1) * 100.0
                if old_year_ago else None
            )
            if yoy is not None and old_yoy is not None:
                trend_delta = yoy - old_yoy

        return yoy, mom, trend_delta

    @staticmethod
    def _unemployment_metrics(history):
        if not history:
            return None, None

        latest = history[0][1]
        change = None

        if len(history) >= 4:
            change = latest - history[3][1]

        return latest, change

    @staticmethod
    def _round(value, digits=3):
        return round(value, digits) if value is not None else None
