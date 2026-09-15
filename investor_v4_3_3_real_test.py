from investor.historical_market_data import HistoricalMarketDataProvider
import pandas as pd
from investor.portfolio_engine import PortfolioAnalyticsEngine, BuyAndHoldBacktester

tickers = ["AAPL", "SLDE", "CRWD"]
weights = {x: 1/3 for x in tickers}

print("=" * 100)
print("V4.3.3 REAL BACKTEST INTEGRITY")
print("=" * 100)

provider = HistoricalMarketDataProvider()
bundle = provider.load(tickers, period="5y", benchmark="SPY")

print("Requested period :", bundle.requested_period)
print("Source           :", bundle.source)
print("Adjusted         :", bundle.adjusted)
print("Provider as-of   :", bundle.as_of)

print("\nPER-SYMBOL HISTORY")
for ticker, meta in bundle.symbol_history.items():
    print(
        ticker,
        "start=", meta["start"],
        "end=", meta["end"],
        "obs=", meta["observations"],
        "years=", meta["calendar_years"],
    )

print("\nBENCHMARK HISTORY")
print(bundle.benchmark_history)

analytics = PortfolioAnalyticsEngine().analyze(
    bundle.prices, weights, bundle.benchmark
)

print("\nCOMMON ALIGNED PORTFOLIO PERIOD")
print("Start            :", analytics.common_start)
print("End              :", analytics.common_end)
print("Calendar years   :", analytics.common_calendar_years)
print("Price observations:", analytics.observations)
print("Return observations:", max(analytics.observations - 1, 0))

bt = BuyAndHoldBacktester().run(
    bundle.prices,
    weights,
    bundle.benchmark,
    initial_capital=100_000,
    transaction_cost_bps=5,
    rebalance="monthly",
    requested_period=bundle.requested_period,
    minimum_history_years=3.0,
    symbol_history=bundle.symbol_history,
    benchmark_history=bundle.benchmark_history,
)

print("\nINTEGRITY")
print("Requested period       :", bt.requested_period)
print("Actual calendar years  :", bt.actual_calendar_years)
print("Minimum required years :", bt.history_requirement_years)
print("History sufficient     :", bt.history_sufficient)
print("Integrity status       :", bt.integrity_status)
print("Warnings               :", bt.warnings)

print("\nBACKTEST (VALID ONLY FOR THE ACTUAL COMMON PERIOD ABOVE)")
print("Start                  :", bt.start)
print("End                    :", bt.end)
print("Ending equity          :", bt.ending_equity)
print("Total return           :", bt.total_return)
print("Annualized return      :", bt.annualized_return)
print("Annualized volatility  :", bt.annualized_volatility)
print("Sharpe                 :", bt.sharpe_ratio)
print("Max drawdown           :", bt.max_drawdown)
print("Benchmark total return :", bt.benchmark_total_return)
print("Benchmark annual return:", bt.benchmark_annualized_return)
print("Benchmark max drawdown :", bt.benchmark_max_drawdown)
print("Trading costs          :", bt.estimated_transaction_cost)
print("Rebalances             :", bt.rebalance_count)

# This exact 3-stock test is expected to expose SLDE's shorter history.
assert bt.actual_calendar_years is not None
assert pd.Timestamp(bt.start) == pd.Timestamp(analytics.common_start)
assert pd.Timestamp(bt.end) == pd.Timestamp(analytics.common_end)

if bt.integrity_status == "LIMITED_HISTORY":
    assert any("Do not describe" in w for w in bt.warnings)

print("\nRESULT: PASS")
