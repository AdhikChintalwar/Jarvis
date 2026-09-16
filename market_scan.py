from __future__ import annotations

import argparse

from investor.scanner import (
    MarketScanner,
    PROFILES,
)


def money(
    value,
):

    if value is None:
        return "N/A"

    if value >= 1_000_000_000:

        return (
            f"${value / 1_000_000_000:.1f}B"
        )

    if value >= 1_000_000:

        return (
            f"${value / 1_000_000:.1f}M"
        )

    return (
        f"${value:,.2f}"
    )


def value(
    number,
    decimals=1,
):

    if number is None:
        return "N/A"

    return (
        f"{number:.{decimals}f}"
    )


def print_candidates(
    summary,
):

    print()

    print(
        "=" * 130
    )

    print(
        f"BABY "
        f"{summary.profile.upper()} "
        f"SCAN"
    )

    print(
        "=" * 130
    )

    print(
        f"Universe: "
        f"{summary.universe_count:,}"
    )

    print(
        f"Market data: "
        f"{summary.market_data_count:,}"
    )

    print(
        f"Eligible: "
        f"{summary.eligibility_count:,}"
    )

    print(
        f"Candidates: "
        f"{summary.quantitative_count:,}"
    )

    print()

    header = (

        f"{'#':<4}"

        f"{'Ticker':<9}"

        f"{'Score':>7}"

        f"{'Flow':>7}"

        f"{'Price':>10}"

        f"{'RVOL':>8}"

        f"{'Z':>7}"

        f"{'Day%':>8}"

        f"{'Gap%':>8}"

        f"{'Close%':>8}"

        f"{'RSI':>7}"

        f"{'ATR%':>8}"

        f"{'Dollar Vol':>15}"
    )

    print(
        header
    )

    print(
        "-" * len(header)
    )

    for index, stock in (
        enumerate(
            summary.candidates,
            start=1,
        )
    ):

        print(

            f"{index:<4}"

            f"{stock.symbol:<9}"

            f"{stock.opportunity_score:>7.1f}"

            f"{stock.flow_score:>7.1f}"

            f"{money(stock.price):>10}"

            f"{value(stock.relative_volume, 2):>8}"

            f"{value(stock.volume_zscore, 1):>7}"

            f"{value(stock.daily_change_pct, 1):>8}"

            f"{value(stock.gap_pct, 1):>8}"

            f"{value(stock.close_location_pct, 0):>8}"

            f"{value(stock.rsi_14, 1):>7}"

            f"{value(stock.atr_pct, 1):>8}"

            f"{money(stock.current_dollar_volume):>15}"
        )

        print(
            f"     FLOW: "
            f"{stock.flow_type}"
        )

        if stock.flags:

            print(
                "     ",
                " | ".join(
                    stock.flags
                ),
            )

    if summary.deep_candidates:

        print()

        print(
            "=" * 130
        )

        print(
            "DEEP BABY ANALYSIS"
        )

        print(
            "=" * 130
        )

        for index, stock in (
            enumerate(
                summary.deep_candidates,
                start=1,
            )
        ):

            print()

            print(
                f"{index}. "
                f"{stock.symbol}"
            )

            print(
                f"   Scanner score: "
                f"{stock.scan_score:.1f}"
            )

            print(
                f"   Decision: "
                f"{stock.decision}"
            )

            print(
                f"   Type: "
                f"{stock.stock_type} / "
                f"{stock.trading_profile}"
            )

            print(
                f"   Financial health: "
                f"{stock.financial_health}"
            )

            print(
                f"   Risk: "
                f"{stock.risk}"
            )

            print(
                f"   Dilution risk: "
                f"{stock.dilution_risk}"
            )

            print(
                f"   RSI: "
                f"{stock.rsi}"
            )

            print(
                f"   RVOL: "
                f"{stock.relative_volume}"
            )

            for reason in (
                stock.reasons[:5]
            ):

                print(
                    f"   • {reason}"
                )


def main():

    parser = (
        argparse.ArgumentParser(
            description=(
                "Baby Investor "
                "U.S. Market Scanner"
            )
        )
    )

    parser.add_argument(

        "profile",

        choices=list(
            PROFILES.keys()
        ),
    )

    parser.add_argument(

        "--limit",

        type=int,

        default=None,

        help=(
            "Testing only. "
            "Uses the first N symbols "
            "alphabetically."
        ),
    )

    parser.add_argument(

        "--top",

        type=int,

        default=30,
    )

    parser.add_argument(

        "--deep",

        type=int,

        default=0,
    )

    parser.add_argument(

        "--batch-size",

        type=int,

        default=100,
    )

    args = (
        parser.parse_args()
    )

    scanner = (
        MarketScanner(
            batch_size=(
                args.batch_size
            )
        )
    )

    summary = (
        scanner.scan(

            profile_name=(
                args.profile
            ),

            limit=(
                args.limit
            ),

            top_n=(
                args.top
            ),

            deep_n=(
                args.deep
            ),
        )
    )

    print_candidates(
        summary
    )


if __name__ == "__main__":
    main()