import sys

from investor import (
    StockAnalyzer,
)


def money(
    value,
):

    if value is None:
        return "N/A"

    return f"${value:,.2f}"


def percent(
    value,
):

    if value is None:
        return "N/A"

    return f"{value:.2f}%"


def number(
    value,
):

    if value is None:
        return "N/A"

    return f"{value:,.0f}"


def heading(
    text,
):

    print()
    print(text)
    print("-" * len(text))


def main():

    ticker = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "NVDA"
    )

    analyzer = (
        StockAnalyzer()
    )

    print()
    print(
        f"Baby Investor analyzing "
        f"{ticker.upper()}..."
    )
    print()

    report = (
        analyzer.analyze(
            ticker
        )
    )

    market = (
        report["market"]
    )

    technical = (
        report["technical"]
    )

    fundamentals = (
        report["fundamentals"]
    )

    risk = (
        report["risk"]
    )

    classification = (
        report[
            "classification"
        ]
    )

    financial = (
        report[
            "financial_health"
        ]
    )

    sec = (
        report["sec"]
    )

    catalysts = (
        report["catalysts"]
    )

    market_context = (
        report[
            "market_context"
        ]
    )

    quality = (
        report[
            "data_quality"
        ]
    )

    thesis = (
        report["thesis"]
    )

    print()
    print("=" * 72)

    print(
        f"{report['company_name']} "
        f"({report['ticker']})"
    )

    print("=" * 72)

    heading(
        "STOCK CLASSIFICATION"
    )

    print(
        "Type:",
        classification
        .stock_type
        .value,
    )

    print(
        "Profile:",
        classification
        .trading_profile
        .value,
    )

    print(
        "Description:",
        classification
        .description,
    )

    print(
        "Speculative:",
        classification
        .is_speculative,
    )

    print(
        "Low float:",
        classification
        .is_low_float,
    )

    heading(
        "MARKET"
    )

    print(
        "Price:",
        money(
            market.current_price
        ),
    )

    print(
        "Daily change:",
        percent(
            market.daily_change_pct
        ),
    )

    print(
        "Volume:",
        number(
            market.volume
        ),
    )

    print(
        "Average volume:",
        number(
            market.average_volume
        ),
    )

    print(
        "Dollar volume:",
        money(
            market.dollar_volume
        ),
    )

    heading(
        "TECHNICAL"
    )

    print(
        "Trend:",
        technical
        .trend_signal
        .value,
    )

    print(
        "Momentum:",
        technical
        .momentum_signal
        .value,
    )

    print(
        "RSI:",
        (
            f"{technical.rsi_14:.2f}"
            if technical.rsi_14
            is not None
            else "N/A"
        ),
    )

    print(
        "Relative volume:",
        (
            f"{technical.relative_volume:.2f}x"
            if technical.relative_volume
            is not None
            else "N/A"
        ),
    )

    print(
        "EMA20:",
        money(
            technical.ema_20
        ),
    )

    print(
        "EMA50:",
        money(
            technical.ema_50
        ),
    )

    print(
        "EMA200:",
        money(
            technical.ema_200
        ),
    )

    print(
        "ATR %:",
        percent(
            technical.atr_percent
        ),
    )

    heading(
        "FINANCIAL HEALTH"
    )

    print(
        "Score:",
        f"{financial.score:.1f}/100",
    )

    print(
        "Growth:",
        f"{financial.revenue_growth_score:.1f}/100",
    )

    print(
        "Profitability:",
        f"{financial.profitability_score:.1f}/100",
    )

    print(
        "Cash flow:",
        f"{financial.cash_flow_score:.1f}/100",
    )

    print(
        "Balance sheet:",
        f"{financial.balance_sheet_score:.1f}/100",
    )

    if (
        financial.cash_runway_years
        is not None
    ):

        print(
            "Estimated cash runway:",
            f"{financial.cash_runway_years:.2f} years",
        )

    for warning in (
        financial.warnings
    ):
        print(
            "⚠",
            warning,
        )

    heading(
        "SEC INTELLIGENCE"
    )

    print(
        "CIK:",
        sec.cik or "Not found",
    )

    print(
        "Dilution risk:",
        sec.dilution_risk.upper(),
    )

    print(
        "Important recent filings:"
    )

    for filing in (
        sec.recent_filings[:10]
    ):

        print(
            f"  {filing.filing_date}  "
            f"{filing.form}"
        )

    if (
        sec.dilution_flags
    ):

        print()
        print(
            "Dilution-related filings:"
        )

        for flag in (
            sec.dilution_flags[:5]
        ):

            print(
                "⚠",
                flag,
            )

    heading(
        "CATALYSTS / NEWS"
    )

    print(
        "Catalyst score:",
        f"{catalysts.catalyst_score:.1f}/100",
    )

    print(
        "Positive:",
        catalysts.positive_count,
        "| Negative:",
        catalysts.negative_count,
        "| High importance:",
        catalysts.high_importance_count,
    )

    for catalyst in (
        catalysts.catalysts[:8]
    ):

        marker = (
            "+"
            if catalyst.category
            == "positive"

            else "-"
            if catalyst.category
            == "negative"

            else "•"
        )

        print(
            f"{marker} "
            f"{catalyst.title}"
        )

    heading(
        "MARKET ENVIRONMENT"
    )

    print(
        "Regime:",
        market_context
        .regime
        .upper(),
    )

    print(
        "Market score:",
        f"{market_context.score:.1f}/100",
    )

    print(
        "SPY:",
        percent(
            market_context
            .spy
            .change_pct
        ),
    )

    print(
        "QQQ:",
        percent(
            market_context
            .qqq
            .change_pct
        ),
    )

    print(
        "IWM:",
        percent(
            market_context
            .iwm
            .change_pct
        ),
    )

    print(
        "VIX:",
        (
            f"{market_context.vix.price:.2f}"
            if market_context.vix.price
            is not None
            else "N/A"
        ),
    )

    heading(
        "RISK"
    )

    print(
        "Overall:",
        risk
        .overall_risk
        .value
        .upper(),
    )

    print(
        "Annual volatility:",
        percent(
            risk.annualized_volatility
        ),
    )

    print(
        "Maximum drawdown:",
        percent(
            risk.max_drawdown
        ),
    )

    print(
        "Liquidity risk:",
        risk
        .liquidity_risk
        .value,
    )

    print(
        "Gap risk:",
        risk
        .gap_risk
        .value,
    )

    for warning in (
        risk.warnings
    ):

        print(
            "⚠",
            warning,
        )

    heading(
        "DATA QUALITY"
    )

    print(
        "Score:",
        f"{quality.score:.1f}/100",
    )

    print(
        "Grade:",
        quality.grade.upper(),
    )

    print(
        "Fields:",
        f"{quality.available_fields}/"
        f"{quality.expected_fields}",
    )

    if quality.missing:

        print(
            "Missing:",
            ", ".join(
                quality.missing
            ),
        )

    heading(
        "BABY INVESTMENT THESIS"
    )

    print(
        "DECISION:",
        thesis.decision,
    )

    print()
    print(
        "BULL CASE"
    )

    for item in (
        thesis.bull_case
    ):
        print(
            "+",
            item,
        )

    print()
    print(
        "BASE CASE"
    )

    for item in (
        thesis.base_case
    ):
        print(
            "•",
            item,
        )

    print()
    print(
        "BEAR CASE"
    )

    for item in (
        thesis.bear_case
    ):
        print(
            "-",
            item,
        )

    print()
    print("=" * 72)


if __name__ == "__main__":
    main()