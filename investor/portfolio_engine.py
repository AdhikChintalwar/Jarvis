from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
import math
from typing import Any

import numpy as np
import pandas as pd


TRADING_DAYS = 252


@dataclass
class PositionRisk:
    ticker: str
    weight: float
    annual_return: float | None
    annual_volatility: float | None
    beta: float | None
    max_drawdown: float | None
    marginal_risk_contribution: float | None
    component_risk_contribution: float | None
    percent_risk_contribution: float | None


@dataclass
class PortfolioRiskReport:
    annual_return: float | None = None
    annual_volatility: float | None = None
    sharpe_ratio: float | None = None
    beta: float | None = None
    max_drawdown: float | None = None

    effective_positions: float | None = None
    largest_weight: float | None = None
    concentration_hhi: float | None = None
    diversification_ratio: float | None = None
    average_pairwise_correlation: float | None = None

    benchmark_return: float | None = None
    benchmark_volatility: float | None = None
    benchmark_max_drawdown: float | None = None
    excess_return: float | None = None
    tracking_error: float | None = None
    information_ratio: float | None = None

    positions: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    unknowns: list[str] = field(default_factory=list)
    observations: int = 0
    common_start: str | None = None
    common_end: str | None = None
    common_calendar_years: float | None = None
    generated_at: str = ""
    schema_version: str = "4.3.3"


@dataclass
class BacktestReport:
    start: str | None = None
    end: str | None = None
    initial_capital: float = 0.0
    ending_equity: float = 0.0
    total_return: float | None = None
    annualized_return: float | None = None
    annualized_volatility: float | None = None
    sharpe_ratio: float | None = None
    max_drawdown: float | None = None

    benchmark_total_return: float | None = None
    benchmark_annualized_return: float | None = None
    benchmark_max_drawdown: float | None = None

    turnover: float = 0.0
    estimated_transaction_cost: float = 0.0
    rebalance_count: int = 0
    observations: int = 0
    requested_period: str | None = None
    actual_calendar_years: float | None = None
    history_sufficient: bool = False
    history_requirement_years: float | None = None
    integrity_status: str = "UNKNOWN"
    symbol_history: dict = field(default_factory=dict)
    benchmark_history: dict | None = None
    warnings: list[str] = field(default_factory=list)
    generated_at: str = ""
    schema_version: str = "4.3.3"


class PortfolioAnalyticsEngine:
    """
    Deterministic portfolio analytics from historical adjusted-price series.

    Input prices:
        DataFrame index = trading dates
        columns = tickers
        values = split/dividend-adjusted prices when available.

    All weights are long-only in V4.3 and normalized to 1.
    This module performs analysis only; it does not create or submit orders.
    """

    def analyze(
        self,
        prices: pd.DataFrame,
        weights: dict[str, float],
        benchmark: pd.Series | None = None,
        risk_free_rate: float = 0.0,
    ) -> PortfolioRiskReport:
        prices, w = self._prepare(prices, weights)
        returns = prices.pct_change(fill_method=None).dropna(how="all")
        returns = returns.dropna()

        if len(returns) < 20:
            raise ValueError("At least 20 complete return observations are required.")

        columns = list(prices.columns)
        wv = np.array([w[c] for c in columns], dtype=float)

        mean_daily = returns.mean().values
        cov_daily = returns.cov().values
        cov_ann = cov_daily * TRADING_DAYS

        port_daily = returns.values @ wv
        annual_return = float(np.mean(port_daily) * TRADING_DAYS)
        variance = float(wv.T @ cov_ann @ wv)
        annual_vol = math.sqrt(max(variance, 0.0))

        sharpe = None
        if annual_vol > 0:
            sharpe = (annual_return - risk_free_rate) / annual_vol

        equity = pd.Series(
            np.cumprod(1.0 + port_daily),
            index=returns.index,
            dtype=float,
        )
        max_dd = self._max_drawdown(equity)

        indiv_vol = np.sqrt(np.maximum(np.diag(cov_ann), 0.0))
        weighted_indiv_vol = float(np.dot(wv, indiv_vol))
        diversification_ratio = (
            weighted_indiv_vol / annual_vol if annual_vol > 0 else None
        )

        corr = returns.corr().values
        pairwise = []
        for i in range(len(columns)):
            for j in range(i + 1, len(columns)):
                x = corr[i, j]
                if np.isfinite(x):
                    pairwise.append(float(x))
        avg_corr = float(np.mean(pairwise)) if pairwise else None

        hhi = float(np.sum(wv ** 2))
        effective = 1.0 / hhi if hhi > 0 else None
        largest = float(np.max(wv))

        # Euler decomposition of portfolio volatility.
        marginal = None
        component = None
        percent = None
        if annual_vol > 0:
            marginal = (cov_ann @ wv) / annual_vol
            component = wv * marginal
            percent = component / annual_vol

        benchmark_return = benchmark_vol = benchmark_dd = None
        excess = tracking_error = info_ratio = None
        beta_portfolio = None
        beta_by_asset = [None] * len(columns)

        if benchmark is not None:
            b = benchmark.copy().astype(float)
            b.name = "benchmark"
            joined = pd.concat(
                [returns, b.pct_change(fill_method=None)],
                axis=1,
                join="inner",
            ).dropna()

            if len(joined) >= 20:
                asset_r = joined[columns]
                br = joined["benchmark"]
                pdaily = asset_r.values @ wv

                benchmark_return = float(br.mean() * TRADING_DAYS)
                benchmark_vol = float(br.std(ddof=1) * math.sqrt(TRADING_DAYS))
                benchmark_equity = (1.0 + br).cumprod()
                benchmark_dd = self._max_drawdown(benchmark_equity)

                active = pd.Series(pdaily, index=joined.index) - br
                excess = float(active.mean() * TRADING_DAYS)
                tracking_error = float(active.std(ddof=1) * math.sqrt(TRADING_DAYS))
                if tracking_error > 0:
                    info_ratio = excess / tracking_error

                bvar = float(br.var(ddof=1))
                if bvar > 0:
                    pser = pd.Series(pdaily, index=joined.index)
                    beta_portfolio = float(pser.cov(br) / bvar)
                    beta_by_asset = [
                        float(asset_r[c].cov(br) / bvar) for c in columns
                    ]

        position_rows = []
        for i, ticker in enumerate(columns):
            series = returns[ticker]
            pos_equity = (1.0 + series).cumprod()
            position_rows.append(asdict(PositionRisk(
                ticker=ticker,
                weight=float(wv[i]),
                annual_return=float(mean_daily[i] * TRADING_DAYS),
                annual_volatility=float(indiv_vol[i]),
                beta=beta_by_asset[i],
                max_drawdown=self._max_drawdown(pos_equity),
                marginal_risk_contribution=(
                    float(marginal[i]) if marginal is not None else None
                ),
                component_risk_contribution=(
                    float(component[i]) if component is not None else None
                ),
                percent_risk_contribution=(
                    float(percent[i]) if percent is not None else None
                ),
            )))

        warnings = []
        if largest >= 0.35:
            warnings.append(
                f"Concentration warning: largest position is {largest:.1%}."
            )
        if effective is not None and effective < min(3.0, len(columns)):
            warnings.append(
                f"Low effective diversification: {effective:.2f} effective positions."
            )
        if avg_corr is not None and avg_corr >= 0.75:
            warnings.append(
                f"High average pairwise correlation: {avg_corr:.2f}."
            )

        # Common-history metadata belongs to the aligned PRICE window.
        # pct_change necessarily removes the first price row, but that must
        # not shift the reported portfolio-history start date.
        common_start = pd.Timestamp(prices.index[0])
        common_end = pd.Timestamp(prices.index[-1])
        common_days = max((common_end - common_start).days, 0)

        return PortfolioRiskReport(
            annual_return=round(annual_return, 6),
            annual_volatility=round(annual_vol, 6),
            sharpe_ratio=self._round(sharpe),
            beta=self._round(beta_portfolio),
            max_drawdown=self._round(max_dd),
            effective_positions=self._round(effective),
            largest_weight=round(largest, 6),
            concentration_hhi=round(hhi, 6),
            diversification_ratio=self._round(diversification_ratio),
            average_pairwise_correlation=self._round(avg_corr),
            benchmark_return=self._round(benchmark_return),
            benchmark_volatility=self._round(benchmark_vol),
            benchmark_max_drawdown=self._round(benchmark_dd),
            excess_return=self._round(excess),
            tracking_error=self._round(tracking_error),
            information_ratio=self._round(info_ratio),
            positions=position_rows,
            warnings=warnings,
            observations=int(len(prices)),
            common_start=self._iso_timestamp(common_start),
            common_end=self._iso_timestamp(common_end),
            common_calendar_years=round(common_days / 365.2425, 4),
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

    def _prepare(self, prices, weights):
        if not isinstance(prices, pd.DataFrame):
            raise TypeError("prices must be a pandas DataFrame")
        if prices.empty:
            raise ValueError("prices cannot be empty")
        if not weights:
            raise ValueError("weights cannot be empty")

        clean_weights = {}
        for ticker, value in weights.items():
            x = float(value)
            if not math.isfinite(x) or x < 0:
                raise ValueError("V4.3 supports finite long-only weights.")
            if x > 0:
                clean_weights[str(ticker)] = x

        if not clean_weights:
            raise ValueError("At least one positive weight is required.")

        missing = [t for t in clean_weights if t not in prices.columns]
        if missing:
            raise ValueError(f"Missing price columns: {missing}")

        total = sum(clean_weights.values())
        clean_weights = {k: v / total for k, v in clean_weights.items()}

        frame = prices[list(clean_weights)].copy()
        frame = frame.apply(pd.to_numeric, errors="coerce")
        frame = frame.replace([np.inf, -np.inf], np.nan)
        frame = frame.ffill().dropna()

        if len(frame) < 21:
            raise ValueError("At least 21 aligned price observations are required.")

        return frame, clean_weights

    @staticmethod
    def _iso_timestamp(value):
        if value is None:
            return None
        return pd.Timestamp(value).isoformat()

    @staticmethod
    def _max_drawdown(equity: pd.Series):
        if equity is None or len(equity) == 0:
            return None
        peak = equity.cummax()
        drawdown = equity / peak - 1.0
        return float(drawdown.min())

    @staticmethod
    def _round(value, digits=6):
        if value is None:
            return None
        try:
            x = float(value)
            return round(x, digits) if math.isfinite(x) else None
        except Exception:
            return None


class BuyAndHoldBacktester:
    """
    Historical simulation with explicit transaction-cost accounting.

    V4.3 semantics:
    - uses only information available at the beginning of the simulation;
    - fixed target weights;
    - optional periodic rebalancing;
    - transaction costs charged on traded notional;
    - no taxes, slippage model, borrow costs, or market impact;
    - no claim that historical performance predicts future results.
    """

    def run(
        self,
        prices: pd.DataFrame,
        weights: dict[str, float],
        benchmark: pd.Series | None = None,
        initial_capital: float = 100_000.0,
        transaction_cost_bps: float = 5.0,
        rebalance: str | None = "monthly",
        risk_free_rate: float = 0.0,
        requested_period: str | None = None,
        minimum_history_years: float = 1.0,
        symbol_history: dict | None = None,
        benchmark_history: dict | None = None,
        strict_history: bool = False,
    ) -> BacktestReport:
        analytics = PortfolioAnalyticsEngine()
        prices, w = analytics._prepare(prices, weights)
        columns = list(prices.columns)
        target = np.array([w[c] for c in columns], dtype=float)

        if initial_capital <= 0:
            raise ValueError("initial_capital must be positive")
        if transaction_cost_bps < 0:
            raise ValueError("transaction_cost_bps cannot be negative")
        if rebalance not in (None, "monthly", "quarterly", "annual"):
            raise ValueError("rebalance must be None/monthly/quarterly/annual")
        if minimum_history_years < 0:
            raise ValueError("minimum_history_years cannot be negative")

        actual_start = pd.Timestamp(prices.index[0])
        actual_end = pd.Timestamp(prices.index[-1])
        actual_days = max((actual_end - actual_start).days, 0)
        actual_years = actual_days / 365.2425
        history_sufficient = actual_years >= minimum_history_years

        requested_years = self._requested_years(requested_period)
        requested_period_satisfied = (
            True if requested_years is None
            else actual_years >= requested_years * 0.90
        )

        if strict_history and not history_sufficient:
            raise ValueError(
                f"Common history {actual_years:.2f}y is below the "
                f"{minimum_history_years:.2f}y minimum."
            )

        cost_rate = transaction_cost_bps / 10_000.0
        first_prices = prices.iloc[0].values.astype(float)

        # Initial allocation cost is charged once.
        initial_trade_notional = float(initial_capital)
        initial_cost = initial_trade_notional * cost_rate
        investable = initial_capital - initial_cost
        shares = investable * target / first_prices
        cash = 0.0

        turnover_notional = initial_trade_notional
        total_cost = initial_cost
        rebalance_count = 0
        equity_values = [initial_capital - initial_cost]
        dates = [prices.index[0]]

        previous_bucket = self._bucket(prices.index[0], rebalance)

        for i in range(1, len(prices)):
            date = prices.index[i]
            px = prices.iloc[i].values.astype(float)

            current_equity = float(np.dot(shares, px) + cash)
            bucket = self._bucket(date, rebalance)

            if rebalance is not None and bucket != previous_bucket:
                desired_values = current_equity * target
                current_values = shares * px
                trades = desired_values - current_values
                traded = float(np.abs(trades).sum())
                cost = traded * cost_rate

                # Recompute desired holdings after transaction cost so the
                # portfolio remains self-financing.
                post_cost_equity = max(current_equity - cost, 0.0)
                desired_values = post_cost_equity * target
                shares = desired_values / px
                cash = 0.0

                turnover_notional += traded
                total_cost += cost
                rebalance_count += 1
                current_equity = post_cost_equity

            equity_values.append(current_equity)
            dates.append(date)
            previous_bucket = bucket

        equity = pd.Series(equity_values, index=dates, dtype=float)
        daily = equity.pct_change(fill_method=None).dropna()

        ending = float(equity.iloc[-1])
        total_return = ending / initial_capital - 1.0
        years = max(actual_years, 1.0 / 365.2425)
        annualized_return = (ending / initial_capital) ** (1.0 / years) - 1.0
        annualized_vol = float(daily.std(ddof=1) * math.sqrt(TRADING_DAYS))
        sharpe = (
            (float(daily.mean()) * TRADING_DAYS - risk_free_rate) / annualized_vol
            if annualized_vol > 0 else None
        )
        max_dd = analytics._max_drawdown(equity)

        benchmark_total = benchmark_ann = benchmark_dd = None
        if benchmark is not None:
            b = benchmark.astype(float).reindex(equity.index).ffill().dropna()
            if len(b) >= 2:
                b = b / b.iloc[0]
                benchmark_total = float(b.iloc[-1] - 1.0)
                bstart = pd.Timestamp(b.index[0])
                bend = pd.Timestamp(b.index[-1])
                byears = max((bend - bstart).days / 365.2425, 1.0 / 365.2425)
                benchmark_ann = float(b.iloc[-1] ** (1.0 / byears) - 1.0)
                benchmark_dd = analytics._max_drawdown(b)

        warnings = [
            "Historical simulation only; past performance is not a forecast.",
            "V4.3.3 excludes taxes, bid/ask spread, market impact, and slippage beyond the configured transaction-cost assumption.",
        ]

        if not history_sufficient:
            warnings.append(
                f"Insufficient common history: {actual_years:.2f} years; "
                f"minimum requirement is {minimum_history_years:.2f} years."
            )

        if requested_years is not None and not requested_period_satisfied:
            warnings.append(
                f"Requested {requested_period} history but the aligned portfolio "
                f"contains only {actual_years:.2f} calendar years. "
                "Do not describe this result as a full requested-period backtest."
            )

        integrity_status = (
            "PASS"
            if history_sufficient and requested_period_satisfied
            else "LIMITED_HISTORY"
        )

        return BacktestReport(
            start=analytics._iso_timestamp(equity.index[0]),
            end=analytics._iso_timestamp(equity.index[-1]),
            initial_capital=round(float(initial_capital), 2),
            ending_equity=round(ending, 2),
            total_return=analytics._round(total_return),
            annualized_return=analytics._round(annualized_return),
            annualized_volatility=analytics._round(annualized_vol),
            sharpe_ratio=analytics._round(sharpe),
            max_drawdown=analytics._round(max_dd),
            benchmark_total_return=analytics._round(benchmark_total),
            benchmark_annualized_return=analytics._round(benchmark_ann),
            benchmark_max_drawdown=analytics._round(benchmark_dd),
            turnover=analytics._round(turnover_notional / initial_capital),
            estimated_transaction_cost=round(total_cost, 2),
            rebalance_count=rebalance_count,
            observations=int(len(equity)),
            requested_period=requested_period,
            actual_calendar_years=round(actual_years, 4),
            history_sufficient=history_sufficient,
            history_requirement_years=round(minimum_history_years, 4),
            integrity_status=integrity_status,
            symbol_history=symbol_history or {},
            benchmark_history=benchmark_history,
            warnings=warnings,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

    @staticmethod
    def _requested_years(period: str | None):
        if not period:
            return None
        p = str(period).strip().lower()
        try:
            if p.endswith("y"):
                return float(p[:-1])
            if p.endswith("mo"):
                return float(p[:-2]) / 12.0
        except Exception:
            return None
        return None

    @staticmethod
    def _bucket(index_value: Any, rebalance: str | None):
        if rebalance is None:
            return None
        ts = pd.Timestamp(index_value)
        if rebalance == "monthly":
            return (ts.year, ts.month)
        if rebalance == "quarterly":
            return (ts.year, (ts.month - 1) // 3 + 1)
        return ts.year
