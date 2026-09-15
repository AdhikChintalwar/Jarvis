import os
import sys
import types
import pandas as pd
import numpy as np

class FakeTicker:
    def __init__(self, symbol):
        self.symbol = symbol
    def history(self, **kwargs):
        n = 30
        base = {"SPY": 500, "QQQ": 450, "IWM": 220, "^VIX": 15}[self.symbol]
        if self.symbol in ("SPY", "QQQ", "IWM"):
            arr = np.linspace(base * .94, base, n)
        else:
            arr = np.linspace(17, 15, n)
        return pd.DataFrame(
            {"Close": arr},
            index=pd.date_range("2026-08-01", periods=n),
        )

yf = types.ModuleType("yfinance")
yf.Ticker = FakeTicker
sys.modules["yfinance"] = yf

os.environ["FRED_API_KEY"] = "x" * 32

from investor.macro_regime import MacroRegimeEngine

engine = MacroRegimeEngine(cache_ttl_seconds=1800)
engine.clear_cache()

# Newest first fixtures.
cpi = []
# Construct 30 monthly levels with inflation cooling into latest month.
dates = pd.date_range("2024-03-01", periods=30, freq="MS")
vals = []
v = 300.0
for i in range(30):
    # earlier faster monthly inflation, latest slower
    monthly = 0.004 if i < 20 else 0.0015
    v *= (1 + monthly)
    vals.append(v)
cpi = [(d.strftime("%Y-%m-%d"), val) for d, val in zip(dates, vals)][::-1]

unrate = [
    ("2026-08-01", 4.1), ("2026-07-01", 4.1),
    ("2026-06-01", 4.2), ("2026-05-01", 4.2),
]
dff = [(f"2026-08-{30-i:02d}", 3.63) for i in range(30)]
dgs2 = [(f"2026-08-{30-i:02d}", 4.20 - i * 0.001) for i in range(30)]
dgs10 = [(f"2026-08-{30-i:02d}", 4.55 - i * 0.001) for i in range(30)]

mapping = {
    "CPIAUCSL": cpi,
    "UNRATE": unrate,
    "DFF": dff,
    "DGS2": dgs2,
    "DGS10": dgs10,
}

calls = {"count": 0}
def fake_history(series, limit=30):
    calls["count"] += 1
    return mapping[series][:limit]

engine._fred_history = fake_history

r1 = engine.analyze(force_refresh=True)
r2 = engine.analyze()

assert r1.coverage == 100.0, r1.coverage
assert r1.cpi_yoy_pct is not None
assert r1.cpi_mom_pct is not None
assert r1.inflation_regime == "cooling", r1.inflation_regime
assert r1.yield_curve_state == "normal", r1.yield_curve_state
assert r1.yield_curve_2s10s_bp > 0
assert r1.fed_funds_rate == 3.63
assert r1.unemployment_rate == 4.1
assert r1.unemployment_change_3m_pp == -0.1
assert calls["count"] == 5, calls
assert r2.cache_age_seconds >= 0
assert r2.generated_at == r1.generated_at

print("V4.0.1 macro semantics + cache contract: PASS")
print("regime:", r1.regime, "score:", r1.score)
print("coverage:", r1.coverage, "confidence:", r1.confidence)
print("CPI YoY:", r1.cpi_yoy_pct, "MoM:", r1.cpi_mom_pct, "state:", r1.inflation_regime)
print("2Y:", r1.treasury_2y, "10Y:", r1.treasury_10y,
      "2s10s bp:", r1.yield_curve_2s10s_bp, "curve:", r1.yield_curve_state)
print("FRED calls after cached second analyze:", calls["count"])
