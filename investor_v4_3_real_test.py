from investor.historical_market_data import HistoricalMarketDataProvider
from investor.portfolio_engine import PortfolioAnalyticsEngine, BuyAndHoldBacktester

tickers = ["AAPL", "SLDE", "CRWD"]
weights = {
    "AAPL": 1/3,
    "SLDE": 1/3,
    "CRWD": 1/3,
}

print("=" * 100)
print("V4.3 REAL PORTFOLIO ANALYSIS")
print("=" * 100)

provider = HistoricalMarketDataProvider()
bundle = provider.load(tickers, period="5y", benchmark="SPY")

print("Source       :", bundle.source)
print("Adjusted     :", bundle.adjusted)
print("As of        :", bundle.as_of)
print("Rows         :", len(bundle.prices))
print("Warnings     :", bundle.warnings)

engine = PortfolioAnalyticsEngine()
r = engine.analyze(
    bundle.prices,
    weights,
    bundle.benchmark,
)

print("\nPORTFOLIO RISK")
print("Annual return          :", r.annual_return)
print("Annual volatility      :", r.annual_volatility)
print("Sharpe                 :", r.sharpe_ratio)
print("Beta                   :", r.beta)
print("Max drawdown           :", r.max_drawdown)
print("Effective positions    :", r.effective_positions)
print("Largest weight         :", r.largest_weight)
print("Concentration HHI      :", r.concentration_hhi)
print("Diversification ratio  :", r.diversification_ratio)
print("Avg pair correlation   :", r.average_pairwise_correlation)
print("Tracking error         :", r.tracking_error)
print("Information ratio      :", r.information_ratio)
print("Warnings               :", r.warnings)
print("Unknowns               :", r.unknowns)

print("\nRISK CONTRIBUTION")
for p in r.positions:
    print(
        p["ticker"],
        "weight=", round(p["weight"], 4),
        "vol=", p["annual_volatility"],
        "beta=", p["beta"],
        "maxDD=", p["max_drawdown"],
        "riskContribution=", p["percent_risk_contribution"],
    )

bt = BuyAndHoldBacktester().run(
    bundle.prices,
    weights,
    bundle.benchmark,
    initial_capital=100_000,
    transaction_cost_bps=5,
    rebalance="monthly",
)

print("\nBACKTEST")
print("Start                   :", bt.start)
print("End                     :", bt.end)
print("Initial capital         :", bt.initial_capital)
print("Ending equity           :", bt.ending_equity)
print("Total return            :", bt.total_return)
print("Annualized return       :", bt.annualized_return)
print("Annualized volatility   :", bt.annualized_volatility)
print("Sharpe                  :", bt.sharpe_ratio)
print("Max drawdown            :", bt.max_drawdown)
print("Benchmark total return  :", bt.benchmark_total_return)
print("Benchmark annual return :", bt.benchmark_annualized_return)
print("Benchmark max drawdown  :", bt.benchmark_max_drawdown)
print("Turnover                :", bt.turnover)
print("Estimated trading costs :", bt.estimated_transaction_cost)
print("Rebalance count         :", bt.rebalance_count)
print("Warnings                :", bt.warnings)

assert bundle.adjusted is True
assert r.observations >= 20
assert r.annual_volatility is not None
assert r.max_drawdown is not None
assert len(r.positions) == 3
assert bt.ending_equity > 0

print("\nRESULT: PASS")
