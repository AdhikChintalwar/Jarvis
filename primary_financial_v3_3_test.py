from __future__ import annotations

import argparse
import json

from investor.primary_data import (
    PrimaryFinancialEngine,
    PrimaryFinancialIntegrationAdapter,
    PrimaryFinancialEvidenceAdapter,
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("ticker")
    parser.add_argument("--full", action="store_true")
    args = parser.parse_args()

    engine = PrimaryFinancialEngine()
    report = engine.analyze_company(args.ticker)

    print("=" * 80)
    print("BABY PRIMARY FINANCIAL INTELLIGENCE V3.3")
    print("=" * 80)
    print("Ticker:", report["ticker"])

    print("\nBALANCE SHEET SNAPSHOT")
    bs = report["balance_sheet_snapshot"]
    print("anchor:", bs["anchor_date"])
    print("status:", bs["status"])
    print("confidence:", bs["confidence"])

    for name, item in bs["metrics"].items():
        print(
            f"{name:28s}: "
            f"{item['value']} | "
            f"{item['date']} | "
            f"{item['status']}"
        )

    print("\nVERIFIED FINANCIALS")
    for name, item in report["verified_financials"].items():
        print(
            f"{name:34s}: "
            f"{item['value']} | "
            f"{item['status']} | "
            f"conf={item['confidence']:.2f}"
        )

    adapter = PrimaryFinancialIntegrationAdapter()
    payload = adapter.to_financial_engine_payload(report)

    print("\nFINANCIAL ENGINE PAYLOAD")
    for key, value in payload.items():
        if key != "primary_financial_evidence":
            print(f"{key:34s}: {value}")

    evidence = PrimaryFinancialEvidenceAdapter().build(report)

    print("\nEVIDENCE")
    print("entries:", len(evidence))
    for key in sorted(evidence):
        item = evidence[key]
        print(
            f"{key:52s} "
            f"value={item.get('value')} "
            f"status={item.get('status')}"
        )

    if args.full:
        print("\nFULL REPORT")
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
