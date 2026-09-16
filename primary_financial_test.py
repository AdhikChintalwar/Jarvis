from __future__ import annotations

import argparse
import json

from investor.primary_data import PrimaryFinancialEngine


def fmt(value):
    return "UNRESOLVED / MISSING" if value is None else str(value)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("ticker")
    parser.add_argument("--diagnostics", action="store_true")
    args = parser.parse_args()

    engine = PrimaryFinancialEngine()
    report = engine.analyze_company(args.ticker)

    print("=" * 80)
    print("BABY PRIMARY FINANCIAL INTELLIGENCE V3.2.1")
    print("=" * 80)
    print("Ticker:", report["ticker"])
    print("Source:", report["source"])
    print()

    for key, value in report["trends"]["metrics"].items():
        print(f"{key:34s}: {fmt(value)}")

    if args.diagnostics:
        print("\nDIAGNOSTICS")
        print(json.dumps(report["trends"]["diagnostics"], indent=2))

        print("\nSELECTED XBRL CONCEPTS / QUALITY")
        for metric, series in report["statements"].items():
            print(
                f"{metric:34s}: "
                f"{series.get('taxonomy')} / "
                f"{series.get('concept')} / "
                f"{series.get('unit')} | "
                f"semantic={series.get('semantic_confidence')} | "
                f"quality={series.get('series_quality')} | "
                f"latest={series.get('latest_economic_date')} | "
                f"calc={series.get('calculation_allowed')}"
            )


if __name__ == "__main__":
    main()
