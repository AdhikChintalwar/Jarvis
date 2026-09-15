from __future__ import annotations

import argparse
import json

from investor.primary_data import PrimaryFinancialEngine


def money(v):
    if v is None:
        return "None"
    a = abs(v)
    if a >= 1e12:
        return f"{v / 1e12:.3f}T"
    if a >= 1e9:
        return f"{v / 1e9:.3f}B"
    if a >= 1e6:
        return f"{v / 1e6:.3f}M"
    return str(v)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("ticker")
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--no-yahoo", action="store_true")
    args = parser.parse_args()

    report = PrimaryFinancialEngine().analyze_company(
        args.ticker,
        validate_secondary=not args.no_yahoo,
    )

    print("=" * 88)
    print("BABY PRIMARY FINANCIAL INTELLIGENCE V3.4")
    print("=" * 88)
    print("Ticker:", report["ticker"])

    bs = report["balance_sheet_snapshot"]
    print("\nBALANCE SHEET")
    print(
        "anchor:", bs["anchor_date"],
        "| status:", bs["status"],
        "| freshness:", bs.get("freshness_days"),
    )

    cv = report.get("cross_validation") or {}
    print("\nCROSS-SOURCE VALIDATION")
    print("confidence:", cv.get("confidence"))
    print("strong_agreements:", cv.get("strong_agreements"))
    print("agreements:", cv.get("agreements"))
    print("reviews:", cv.get("reviews"))
    print("disagreements:", cv.get("disagreements"))
    print("primary_only:", cv.get("primary_only"))
    print("secondary_only:", cv.get("secondary_only"))

    for metric, item in (cv.get("metrics") or {}).items():
        diff = item.get("difference")
        diff_text = "None" if diff is None else f"{diff:.6f}"
        print(
            f"{metric:24s} "
            f"SEC={money(item.get('primary_value')):>12s} "
            f"YH={money(item.get('secondary_value')):>12s} "
            f"P={str(item.get('primary_period')):10s} "
            f"S={str(item.get('secondary_period')):10s} "
            f"{item.get('period_status'):18s} "
            f"{item.get('status'):36s} "
            f"diff={diff_text}"
        )

    print("\nVERIFIED FINANCIALS")
    for metric, item in report["verified_financials"].items():
        print(
            f"{metric:34s}: "
            f"{money(item.get('value')):>12s} | "
            f"{item.get('status'):36s} | "
            f"conf={item.get('confidence', 0):.2f}"
        )

    if args.full:
        print("\nFULL REPORT")
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
