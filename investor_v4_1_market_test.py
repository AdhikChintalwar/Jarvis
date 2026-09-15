import sys, types
import numpy as np
import pandas as pd

def frame(start, end, volume=1_000_000, n=252):
    close = np.linspace(start, end, n)
    vol = np.full(n, volume, dtype=float)
    vol[-1] = volume * 1.8
    return pd.DataFrame(
        {"Close": close, "Volume": vol},
        index=pd.date_range("2025-09-01", periods=n, freq="B"),
    )

fixtures = {
    "SPY": frame(400, 500),
    "QQQ": frame(350, 460),
    "IWM": frame(180, 220),
    "RSP": frame(140, 180),
    "XLK": frame(200, 240),
}
fixtures["XLK"].loc[fixtures["XLK"].index[-61]:, "Close"] = np.linspace(
    float(fixtures["XLK"]["Close"].iloc[-61]),
    275.0,
    61,
)

class FakeTicker:
    def __init__(self, symbol): self.symbol = symbol
    def history(self, **kwargs): return fixtures[self.symbol]

yf = types.ModuleType("yfinance")
yf.Ticker = FakeTicker
sys.modules["yfinance"] = yf

from investor.advanced_market_intelligence import AdvancedMarketIntelligenceEngine

stock = frame(100, 140)
# Explicit recent acceleration versus SPY.
stock.loc[stock.index[-61]:, "Close"] = np.linspace(
    float(stock["Close"].iloc[-61]),
    175.0,
    61,
)
engine = AdvancedMarketIntelligenceEngine()
report = engine.analyze(
    ticker="TEST",
    stock_history=stock,
    company_info={"sector": "Technology"},
)

assert report.coverage == 100.0, report.coverage
assert report.breadth_regime == "broad_participation", report.breadth_regime
assert report.sector_etf == "XLK"
assert report.stock_relative_strength == "outperforming", report.stock_relative_strength
assert report.sector_regime == "supportive", report.sector_regime
assert report.participation_regime == "elevated", report.participation_regime
assert report.score > 50
assert "stock_relative_strength" in report.signals
assert "stock_vs_sector_20d" in report.signals

print("V4.1 advanced-market contract: PASS")
print("score:", report.score, "confidence:", report.confidence, "coverage:", report.coverage)
print("structure:", report.market_structure)
print("breadth:", report.breadth_regime)
print("relative strength:", report.stock_relative_strength)
print("sector:", report.sector, report.sector_etf, report.sector_regime)
print("participation:", report.participation_regime)
print("volatility:", report.volatility_state)
