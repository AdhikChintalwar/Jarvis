import sys, types
if "yfinance" not in sys.modules:
    yf = types.ModuleType("yfinance")
    yf.download = lambda *args, **kwargs: None
    class _Ticker:
        def __init__(self, *args, **kwargs): pass
    yf.Ticker = _Ticker
    sys.modules["yfinance"] = yf

import numpy as np
import pandas as pd

from investor.portfolio_engine import PortfolioAnalyticsEngine, BuyAndHoldBacktester

rng = np.random.default_rng(7)

# Five years exist for AAA/BBB, but CCC begins only ~15 months before the end.
dates = pd.bdate_range("2021-09-16", "2026-09-15")
n = len(dates)

def make_price(mu, sigma, start):
    r = rng.normal(mu, sigma, n)
    return start * np.cumprod(1 + r)

full = pd.DataFrame({
    "AAA": make_price(.0004, .012, 100),
    "BBB": make_price(.0003, .010, 80),
    "CCC": make_price(.0005, .018, 40),
}, index=dates)

cutoff = pd.Timestamp("2025-06-18")
full.loc[full.index < cutoff, "CCC"] = np.nan

benchmark = pd.Series(make_price(.0003, .009, 100), index=dates, name="benchmark")
weights = {"AAA": 1/3, "BBB": 1/3, "CCC": 1/3}

engine = PortfolioAnalyticsEngine()
analytics = engine.analyze(full, weights, benchmark)

bt = BuyAndHoldBacktester().run(
    full,
    weights,
    benchmark,
    requested_period="5y",
    minimum_history_years=3.0,
    initial_capital=100_000,
    transaction_cost_bps=5,
)

assert analytics.common_calendar_years < 2.0, analytics.common_calendar_years
assert bt.actual_calendar_years < 2.0, bt.actual_calendar_years
assert bt.history_sufficient is False
assert bt.integrity_status == "LIMITED_HISTORY"
assert any("Requested 5y" in w for w in bt.warnings)
assert any("Insufficient common history" in w for w in bt.warnings)

# Strict mode must refuse to present the short common history as sufficient.
try:
    BuyAndHoldBacktester().run(
        full,
        weights,
        benchmark,
        requested_period="5y",
        minimum_history_years=3.0,
        strict_history=True,
    )
    raise AssertionError("strict_history should have failed")
except ValueError as exc:
    assert "below" in str(exc)

# Full-history control should pass.
control = full[["AAA", "BBB"]]
control_bt = BuyAndHoldBacktester().run(
    control,
    {"AAA": .5, "BBB": .5},
    benchmark,
    requested_period="5y",
    minimum_history_years=3.0,
)
assert control_bt.history_sufficient is True
assert control_bt.integrity_status == "PASS"
assert control_bt.actual_calendar_years >= 4.9

print("V4.3.1 backtest-integrity contract: PASS")
print("truncated common years:", bt.actual_calendar_years)
print("truncated status:", bt.integrity_status)
print("full control years:", control_bt.actual_calendar_years)
print("full control status:", control_bt.integrity_status)
print("warnings:", bt.warnings)
