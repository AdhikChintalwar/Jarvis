from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
import math
import numpy as np
import pandas as pd
import yfinance as yf


@dataclass
class MarketSignal:
    name: str
    value: float | None = None
    state: str = "unknown"
    confidence: float = 0.0
    as_of: str | None = None
    source: str = ""
    metadata: dict = field(default_factory=dict)


@dataclass
class AdvancedMarketReport:
    score: float = 50.0
    confidence: float = 0.0
    coverage: float = 0.0

    market_structure: str = "unknown"
    breadth_regime: str = "unknown"
    stock_relative_strength: str = "unknown"
    sector_regime: str = "unknown"
    participation_regime: str = "unknown"
    volatility_state: str = "unknown"

    sector: str | None = None
    sector_etf: str | None = None

    signals: dict = field(default_factory=dict)
    positives: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    unknowns: list[str] = field(default_factory=list)

    generated_at: str = ""
    schema_version: str = "4.1"


class AdvancedMarketIntelligenceEngine:
    """
    Deterministic cross-sectional / relative market layer.

    This version is intentionally evidence-only:
    it does NOT alter StockScore yet.

    Yahoo is a secondary/prototype market-data source. Every derived signal
    therefore has capped authority. Missing data remains neutral.
    """

    SECTOR_ETFS = {
        "Technology": "XLK",
        "Information Technology": "XLK",
        "Communication Services": "XLC",
        "Consumer Cyclical": "XLY",
        "Consumer Discretionary": "XLY",
        "Consumer Defensive": "XLP",
        "Consumer Staples": "XLP",
        "Financial Services": "XLF",
        "Financials": "XLF",
        "Healthcare": "XLV",
        "Health Care": "XLV",
        "Industrials": "XLI",
        "Energy": "XLE",
        "Basic Materials": "XLB",
        "Materials": "XLB",
        "Real Estate": "XLRE",
        "Utilities": "XLU",
    }

    BREADTH_ETFS = ("SPY", "QQQ", "IWM", "RSP")

    def analyze(self, ticker: str, stock_history, company_info: dict | None = None):
        ticker = ticker.upper().strip()
        info = company_info or {}

        signals = {}
        positives, risks, unknowns = [], [], []
        contributions = []

        def add(name, value, state, confidence, as_of, source, metadata=None):
            signals[name] = MarketSignal(
                name=name,
                value=self._finite(value),
                state=state,
                confidence=round(confidence, 3),
                as_of=as_of,
                source=source,
                metadata=metadata or {},
            )

        def pressure(points, signal_name, text):
            sig = signals.get(signal_name)
            if not sig or sig.value is None or sig.confidence <= 0:
                return
            contributions.append(points * sig.confidence)
            (positives if points > 0 else risks).append(text)

        # ---------- broad market breadth / structure ----------
        breadth_frames = {}
        for symbol in self.BREADTH_ETFS:
            breadth_frames[symbol] = self._history(symbol)

        breadth_known = []
        for symbol, frame in breadth_frames.items():
            stats = self._trend_stats(frame)
            add(
                f"{symbol.lower()}_trend",
                stats["return_20d"],
                stats["state"],
                0.70 if stats["return_20d"] is not None else 0.0,
                stats["as_of"],
                "Yahoo market proxy",
                {
                    "return_60d_pct": stats["return_60d"],
                    "above_50dma": stats["above_50dma"],
                    "above_200dma": stats["above_200dma"],
                },
            )
            if stats["return_20d"] is not None:
                breadth_known.append(stats)

        if len(breadth_known) >= 3:
            above50 = sum(x["above_50dma"] is True for x in breadth_known)
            below50 = sum(x["above_50dma"] is False for x in breadth_known)
            positive20 = sum((x["return_20d"] or 0) > 0 for x in breadth_known)

            if above50 >= 3 and positive20 >= 3:
                breadth_regime = "broad_participation"
            elif below50 >= 3 and positive20 <= 1:
                breadth_regime = "broad_weakness"
            else:
                breadth_regime = "mixed"

            breadth_value = above50 / len(breadth_known) * 100
            add(
                "breadth",
                breadth_value,
                breadth_regime,
                0.70,
                max((x["as_of"] for x in breadth_known if x["as_of"]), default=None),
                "Derived from Yahoo ETF proxies",
                {
                    "etfs_known": len(breadth_known),
                    "above_50dma_count": above50,
                    "positive_20d_count": positive20,
                },
            )

            if breadth_regime == "broad_participation":
                pressure(10, "breadth", "Broad market participation is constructive.")
            elif breadth_regime == "broad_weakness":
                pressure(-10, "breadth", "Broad market participation is weak.")
        else:
            breadth_regime = "unknown"
            unknowns.append("market_breadth")

        # Equal-weight vs cap-weight is useful concentration/participation evidence.
        rsp = breadth_frames.get("RSP")
        spy = breadth_frames.get("SPY")
        rsp20 = self._return_pct(rsp, 20)
        spy20 = self._return_pct(spy, 20)
        if rsp20 is not None and spy20 is not None:
            spread = rsp20 - spy20
            state = "broadening" if spread > 1 else "narrowing" if spread < -1 else "balanced"
            as_of = self._as_of(rsp)
            add("equal_weight_vs_spy_20d", spread, state, 0.70, as_of,
                "Derived from Yahoo RSP/SPY proxies")
            if state == "broadening":
                pressure(5, "equal_weight_vs_spy_20d", "Equal-weight participation is improving versus SPY.")
            elif state == "narrowing":
                pressure(-5, "equal_weight_vs_spy_20d", "Market leadership is narrowing versus equal weight.")
        else:
            unknowns.append("equal_weight_participation")

        # ---------- stock relative strength ----------
        stock20 = self._return_pct(stock_history, 20)
        stock60 = self._return_pct(stock_history, 60)
        spy20 = self._return_pct(spy, 20)
        spy60 = self._return_pct(spy, 60)

        if stock20 is not None and spy20 is not None:
            rs20 = stock20 - spy20
            rs60 = stock60 - spy60 if stock60 is not None and spy60 is not None else None
            if rs20 >= 5 and (rs60 is None or rs60 >= 0):
                rs_state = "outperforming"
            elif rs20 <= -5 and (rs60 is None or rs60 <= 0):
                rs_state = "underperforming"
            else:
                rs_state = "mixed"

            add(
                "stock_relative_strength",
                rs20,
                rs_state,
                0.70,
                self._as_of(stock_history),
                "Derived from stock and SPY Yahoo histories",
                {
                    "stock_20d_pct": stock20,
                    "spy_20d_pct": spy20,
                    "relative_60d_pct": rs60,
                },
            )
            if rs_state == "outperforming":
                pressure(12, "stock_relative_strength", f"{ticker} is outperforming SPY.")
            elif rs_state == "underperforming":
                pressure(-12, "stock_relative_strength", f"{ticker} is underperforming SPY.")
        else:
            rs_state = "unknown"
            unknowns.append("stock_relative_strength")

        # ---------- sector regime + stock vs sector ----------
        sector = info.get("sector")
        sector_etf = self.SECTOR_ETFS.get(sector)
        sector_regime = "unknown"

        if sector_etf:
            sector_history = self._history(sector_etf)
            sec_stats = self._trend_stats(sector_history)
            add(
                "sector_trend",
                sec_stats["return_20d"],
                sec_stats["state"],
                0.65 if sec_stats["return_20d"] is not None else 0.0,
                sec_stats["as_of"],
                f"Yahoo sector ETF proxy:{sector_etf}",
                {
                    "sector": sector,
                    "return_60d_pct": sec_stats["return_60d"],
                    "above_50dma": sec_stats["above_50dma"],
                },
            )

            if sec_stats["return_20d"] is not None:
                if sec_stats["return_20d"] > 2 and sec_stats["above_50dma"]:
                    sector_regime = "supportive"
                    pressure(7, "sector_trend", f"{sector_etf} sector trend is supportive.")
                elif sec_stats["return_20d"] < -2 and sec_stats["above_50dma"] is False:
                    sector_regime = "weak"
                    pressure(-7, "sector_trend", f"{sector_etf} sector trend is weak.")
                else:
                    sector_regime = "mixed"

            sector20 = self._return_pct(sector_history, 20)
            if stock20 is not None and sector20 is not None:
                stock_sector_spread = stock20 - sector20
                state = (
                    "outperforming_sector" if stock_sector_spread >= 5
                    else "underperforming_sector" if stock_sector_spread <= -5
                    else "in_line"
                )
                add(
                    "stock_vs_sector_20d",
                    stock_sector_spread,
                    state,
                    0.65,
                    self._as_of(stock_history),
                    f"Derived from stock and {sector_etf} Yahoo histories",
                )
                if state == "outperforming_sector":
                    pressure(7, "stock_vs_sector_20d", f"{ticker} is outperforming its sector proxy.")
                elif state == "underperforming_sector":
                    pressure(-7, "stock_vs_sector_20d", f"{ticker} is underperforming its sector proxy.")
        else:
            unknowns.append("sector_mapping")

        # ---------- participation / volume ----------
        participation = self._participation(stock_history)
        if participation["relative_volume_20d"] is not None:
            rv = participation["relative_volume_20d"]
            if rv >= 1.5:
                p_state = "elevated"
            elif rv <= 0.65:
                p_state = "thin"
            else:
                p_state = "normal"

            add(
                "relative_volume_20d",
                rv,
                p_state,
                0.65,
                self._as_of(stock_history),
                "Derived from Yahoo stock history",
                {
                    "up_volume_ratio_20d": participation["up_volume_ratio_20d"],
                    "volume_zscore_20d": participation["volume_zscore_20d"],
                },
            )

            # Volume itself is not directional. Direction requires price confirmation.
            latest_return = participation["latest_return_pct"]
            if rv >= 1.5 and latest_return is not None:
                if latest_return >= 1:
                    pressure(5, "relative_volume_20d", "Elevated volume accompanies positive price action.")
                elif latest_return <= -1:
                    pressure(-5, "relative_volume_20d", "Elevated volume accompanies negative price action.")
        else:
            p_state = "unknown"
            unknowns.append("volume_participation")

        # ---------- realized volatility ----------
        vol = self._realized_vol(stock_history)
        if vol is not None:
            if vol >= 80:
                vol_state = "very_high"
                vol_points = -8
            elif vol >= 50:
                vol_state = "high"
                vol_points = -5
            elif vol <= 20:
                vol_state = "low"
                vol_points = 2
            else:
                vol_state = "normal"
                vol_points = 0

            add(
                "realized_volatility_20d",
                vol,
                vol_state,
                0.70,
                self._as_of(stock_history),
                "Derived from Yahoo stock history",
                {"unit": "annualized_percent"},
            )
            if vol_points:
                pressure(
                    vol_points,
                    "realized_volatility_20d",
                    f"{ticker} realized volatility is {vol_state.replace('_', ' ')}.",
                )
        else:
            vol_state = "unknown"
            unknowns.append("realized_volatility")

        # ---------- synthesis ----------
        score = 50.0 + sum(contributions)
        score = max(0.0, min(100.0, score))

        if score >= 65:
            market_structure = "supportive"
        elif score <= 35:
            market_structure = "adverse"
        else:
            market_structure = "mixed"

        desired = (
            "breadth",
            "equal_weight_vs_spy_20d",
            "stock_relative_strength",
            "sector_trend",
            "stock_vs_sector_20d",
            "relative_volume_20d",
            "realized_volatility_20d",
        )
        available = [signals[k] for k in desired if k in signals and signals[k].value is not None]
        coverage = len(available) / len(desired) * 100.0
        confidence = (
            sum(x.confidence for x in available) / len(available) * 100.0
            if available else 0.0
        )

        return AdvancedMarketReport(
            score=round(score, 2),
            confidence=round(confidence, 2),
            coverage=round(coverage, 2),
            market_structure=market_structure,
            breadth_regime=breadth_regime,
            stock_relative_strength=rs_state,
            sector_regime=sector_regime,
            participation_regime=p_state,
            volatility_state=vol_state,
            sector=sector,
            sector_etf=sector_etf,
            signals={k: asdict(v) for k, v in signals.items()},
            positives=positives,
            risks=risks,
            unknowns=unknowns,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

    def _history(self, symbol):
        try:
            data = yf.Ticker(symbol).history(
                period="1y",
                interval="1d",
                auto_adjust=False,
            )
            return data if data is not None and len(data) else None
        except Exception:
            return None

    @staticmethod
    def _close(frame):
        if frame is None or "Close" not in frame:
            return None
        s = frame["Close"].dropna()
        return s if len(s) else None

    def _return_pct(self, frame, sessions):
        close = self._close(frame)
        if close is None or len(close) < sessions + 1:
            return None
        old = float(close.iloc[-(sessions + 1)])
        current = float(close.iloc[-1])
        if old == 0:
            return None
        return round((current / old - 1) * 100.0, 4)

    def _trend_stats(self, frame):
        close = self._close(frame)
        if close is None:
            return {
                "return_20d": None, "return_60d": None,
                "above_50dma": None, "above_200dma": None,
                "state": "unknown", "as_of": None,
            }

        r20 = self._return_pct(frame, 20)
        r60 = self._return_pct(frame, 60)
        current = float(close.iloc[-1])
        ma50 = float(close.iloc[-50:].mean()) if len(close) >= 50 else None
        ma200 = float(close.iloc[-200:].mean()) if len(close) >= 200 else None

        above50 = current > ma50 if ma50 is not None else None
        above200 = current > ma200 if ma200 is not None else None

        if r20 is None:
            state = "unknown"
        elif r20 > 2 and above50 is not False:
            state = "rising"
        elif r20 < -2 and above50 is not True:
            state = "falling"
        else:
            state = "mixed"

        return {
            "return_20d": r20,
            "return_60d": r60,
            "above_50dma": above50,
            "above_200dma": above200,
            "state": state,
            "as_of": self._as_of(frame),
        }

    @staticmethod
    def _participation(frame):
        result = {
            "relative_volume_20d": None,
            "up_volume_ratio_20d": None,
            "volume_zscore_20d": None,
            "latest_return_pct": None,
        }
        if frame is None or "Volume" not in frame or "Close" not in frame:
            return result

        volume = frame["Volume"].dropna()
        close = frame["Close"].dropna()
        if len(volume) < 21 or len(close) < 2:
            return result

        baseline = volume.iloc[-21:-1]
        mean = float(baseline.mean())
        std = float(baseline.std(ddof=0))
        latest = float(volume.iloc[-1])

        result["relative_volume_20d"] = round(latest / mean, 4) if mean > 0 else None
        result["volume_zscore_20d"] = round((latest - mean) / std, 4) if std > 0 else None
        result["latest_return_pct"] = round(
            (float(close.iloc[-1]) / float(close.iloc[-2]) - 1) * 100.0, 4
        )

        aligned = frame[["Close", "Volume"]].dropna().iloc[-21:]
        if len(aligned) >= 2:
            ret = aligned["Close"].pct_change()
            vol = aligned["Volume"]
            total = float(vol.iloc[1:].sum())
            up = float(vol.iloc[1:][ret.iloc[1:] > 0].sum())
            result["up_volume_ratio_20d"] = round(up / total, 4) if total > 0 else None

        return result

    @staticmethod
    def _realized_vol(frame):
        if frame is None or "Close" not in frame:
            return None
        close = frame["Close"].dropna()
        if len(close) < 22:
            return None
        returns = np.log(close / close.shift(1)).dropna().iloc[-20:]
        if len(returns) < 15:
            return None
        return round(float(returns.std(ddof=0) * math.sqrt(252) * 100.0), 4)

    @staticmethod
    def _as_of(frame):
        if frame is None or len(frame) == 0:
            return None
        idx = frame.index[-1]
        return idx.isoformat() if hasattr(idx, "isoformat") else str(idx)

    @staticmethod
    def _finite(value):
        if value is None:
            return None
        try:
            value = float(value)
            return value if math.isfinite(value) else None
        except Exception:
            return None
