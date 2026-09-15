from __future__ import annotations

import argparse
import json

from investor.primary_data import PrimaryFinancialEngine


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("ticker")
    parser.add_argument("--full", action="store_true")
    args = parser.parse_args()

    report = PrimaryFinancialEngine().analyze_company(args.ticker)
    bs = report["balance_sheet_snapshot"]

    print("=" * 80)
    print("BABY PRIMARY FINANCIAL INTELLIGENCE V3.3.1")
    print("=" * 80)
    print("Ticker:", report["ticker"])
    print("anchor:", bs["anchor_date"])
    print("status:", bs["status"])
    print("freshness_days:", bs.get("freshness_days"))
    print("core_coverage:", bs.get("core_coverage"))
    print("optional_coverage:", bs.get("optional_coverage"))
    print("confidence:", bs["confidence"])

    print("\nBALANCE SHEET")
    for name, item in bs["metrics"].items():
        print(
            f"{name:28s}: {item['value']} | "
            f"{item['date']} | {item['status']} | "
            f"conf={item['confidence']:.3f}"
        )

    print("\nSELECTION DIAGNOSTICS")
    diagnostics = bs.get("diagnostics", {})
    print("newest_core_date:", diagnostics.get("newest_core_date"))
    print("selected_anchor:", diagnostics.get("selected_anchor"))
    print("selected_age_days:", diagnostics.get("selected_age_days"))
    print("selected_score:", diagnostics.get("selected_score"))

    print("\nTOP CANDIDATE SNAPSHOTS")
    for row in diagnostics.get("candidate_scores", [])[:8]:
        print(
            f"{row['anchor']} | score={row['score']} | "
            f"age={row['age_days']}d | "
            f"core={row['core_coverage']} | "
            f"optional={row['optional_coverage']} | "
            f"recency={row['recency_score']}"
        )

    print("\nVERIFIED")
    for name in (
        "cash",
        "short_term_investments",
        "cash_plus_short_term_investments",
        "debt",
        "cash_to_debt",
        "liquid_assets_to_debt",
        "shares_change_yoy",
    ):
        item = report["verified_financials"].get(name, {})
        print(
            f"{name:34s}: {item.get('value')} | "
            f"{item.get('status')} | "
            f"conf={item.get('confidence', 0):.2f}"
        )

    if args.full:
        print("\nFULL REPORT")
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
