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

rng = np.random.default_rng(42)
n = 504
dates = pd.bdate_range("2024-01-02", periods=n)

market = rng.normal(0.00035, 0.009, n)
a = 0.00025 + 0.85 * market + rng.normal(0, 0.005, n)
b = 0.00020 + 0.45 * market + rng.normal(0, 0.008, n)
c = 0.00015 + 0.15 * market + rng.normal(0, 0.011, n)

def price(r, start):
    return start * np.cumprod(1 + r)

prices = pd.DataFrame({
    "AAA": price(a, 100),
    "BBB": price(b, 80),
    "CCC": price(c, 60),
}, index=dates)
benchmark = pd.Series(price(market, 100), index=dates, name="benchmark")

weights = {"AAA": 0.50, "BBB": 0.30, "CCC": 0.20}

engine = PortfolioAnalyticsEngine()
report = engine.analyze(prices, weights, benchmark)

assert report.observations >= 500
assert report.annual_volatility > 0
assert report.max_drawdown <= 0
assert report.beta is not None
assert report.effective_positions > 1
assert report.diversification_ratio >= 1.0
assert len(report.positions) == 3
assert abs(sum(p["percent_risk_contribution"] for p in report.positions) - 1.0) < 1e-6

backtester = BuyAndHoldBacktester()
bt = backtester.run(
    prices,
    weights,
    benchmark,
    initial_capital=100_000,
    transaction_cost_bps=5,
    rebalance="monthly",
)
assert bt.ending_equity > 0
assert bt.estimated_transaction_cost > 0
assert bt.rebalance_count > 0
assert bt.max_drawdown <= 0
assert bt.benchmark_total_return is not None

# Transaction costs must reduce ending wealth versus a zero-cost identical run.
bt_free = backtester.run(
    prices,
    weights,
    benchmark,
    initial_capital=100_000,
    transaction_cost_bps=0,
    rebalance="monthly",
)
assert bt.ending_equity < bt_free.ending_equity

print("V4.3 portfolio/backtest contract: PASS")
print("portfolio annual return:", report.annual_return)
print("portfolio volatility:", report.annual_volatility)
print("portfolio beta:", report.beta)
print("max drawdown:", report.max_drawdown)
print("effective positions:", report.effective_positions)
print("avg correlation:", report.average_pairwise_correlation)
print("backtest ending equity:", bt.ending_equity)
print("transaction costs:", bt.estimated_transaction_cost)
print("rebalances:", bt.rebalance_count)
