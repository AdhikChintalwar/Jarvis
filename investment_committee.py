from __future__ import annotations

import argparse
from pathlib import Path

from investor.committee import (
    InvestmentCommitteePipeline,
)


def find_latest_scan(
    profile: str,
):

    path = (
        Path("data/scans")
        / f"{profile}_latest.json"
    )

    if not path.exists():

        raise FileNotFoundError(
            f"No latest scan found: "
            f"{path}"
        )

    return str(
        path
    )

def print_report(report):
    """
    Print Baby Investment Committee results.

    Supports:
    - CommitteeReport dataclass objects
    - dict reports
    - CommitteeRanking dataclasses
    - dict rankings
    """

    def get_value(obj, key, default=None):
        if obj is None:
            return default

        if isinstance(obj, dict):
            return obj.get(key, default)

        return getattr(
            obj,
            key,
            default,
        )

    print()
    print("=" * 100)
    print("BABY INVESTMENT COMMITTEE")
    print("=" * 100)

    candidates_processed = get_value(
        report,
        "candidates_processed",
        0,
    )

    candidates_passed = get_value(
        report,
        "candidates_passed",
        0,
    )

    print(
        f"Candidates processed: "
        f"{candidates_processed}"
    )

    print(
        f"Candidates passed: "
        f"{candidates_passed}"
    )

    market_summary = get_value(
        report,
        "market_summary",
        "",
    )

    if market_summary:
        print()
        print("MARKET SUMMARY")
        print(market_summary)

    committee_summary = get_value(
        report,
        "committee_summary",
        "",
    )

    if committee_summary:
        print()
        print("COMMITTEE SUMMARY")
        print(committee_summary)

    print()
    print("=" * 100)
    print("FINAL RANKING")
    print("=" * 100)
    print()

    rankings = get_value(
        report,
        "rankings",
        [],
    ) or []

    if not rankings:
        print(
            "No candidates reached "
            "the final ranking."
        )

    for ranking in rankings:

        rank = get_value(
            ranking,
            "rank",
            0,
        )

        symbol = get_value(
            ranking,
            "symbol",
            "UNKNOWN",
        )

        committee_score = get_value(
            ranking,
            "committee_score",
            0,
        )

        decision = get_value(
            ranking,
            "decision",
            "WATCH",
        )

        confidence = get_value(
            ranking,
            "confidence",
            0,
        )

        integrity_score = get_value(
            ranking,
            "integrity_score",
            None,
        )

        integrity_passed = get_value(
            ranking,
            "integrity_passed",
            None,
        )

        strongest_strength = get_value(
            ranking,
            "strongest_strength",
            "",
        )

        biggest_risk = get_value(
            ranking,
            "biggest_risk",
            "",
        )

        why_ranked_here = get_value(
            ranking,
            "why_ranked_here",
            "",
        )

        preferred_action = get_value(
            ranking,
            "preferred_action",
            "",
        )

        unknowns = get_value(
            ranking,
            "unknowns",
            [],
        ) or []

        supported_claims = get_value(
            ranking,
            "supported_claims",
            [],
        ) or []

        unsupported_claims = get_value(
            ranking,
            "unsupported_claims",
            [],
        ) or []

        evidence_used = get_value(
            ranking,
            "evidence_used",
            [],
        ) or []

        print(
            f"#{rank} {symbol}"
        )

        print(
            f"Committee score: "
            f"{float(committee_score):.1f}"
        )

        print(
            f"Decision: "
            f"{decision}"
        )

        print(
            f"Confidence: "
            f"{float(confidence):.1f}"
        )

        if integrity_score is not None:

            print(
                f"Evidence integrity: "
                f"{float(integrity_score):.1f}%"
            )

        if integrity_passed is not None:

            status = (
                "PASS"
                if integrity_passed
                else "WARN"
            )

            print(
                f"Integrity status: "
                f"{status}"
            )

        if strongest_strength:

            print(
                f"Strength: "
                f"{strongest_strength}"
            )

        if biggest_risk:

            print(
                f"Risk: "
                f"{biggest_risk}"
            )

        if why_ranked_here:

            print(
                f"Why: "
                f"{why_ranked_here}"
            )

        if preferred_action:

            print(
                f"Action: "
                f"{preferred_action}"
            )

        if unknowns:

            print()
            print(
                "UNKNOWN / NEEDS DATA:"
            )

            for item in unknowns:
                print(
                    f"  ? {item}"
                )

        #
        # Evidence Integrity V2.1 audit
        #

        print()
        print(
            "CLAIM AUDIT"
        )

        print(
            f"  Supported claims: "
            f"{len(supported_claims)}"
        )

        print(
            f"  Rejected claims: "
            f"{len(unsupported_claims)}"
        )

        print(
            f"  Evidence items used: "
            f"{len(evidence_used)}"
        )

        if unsupported_claims:

            print()
            print(
                "REJECTED / UNSUPPORTED CLAIMS"
            )

            for claim in unsupported_claims:

                statement = get_value(
                    claim,
                    "statement",
                    "",
                )

                reason = get_value(
                    claim,
                    "validation_reason",
                    "",
                )

                if statement:
                    print(
                        f"  ✗ {statement}"
                    )

                if reason:
                    print(
                        f"    Reason: "
                        f"{reason}"
                    )

        print()
        print("-" * 100)
        print()

    watch_list = get_value(
        report,
        "watch_list",
        [],
    ) or []

    avoid_list = get_value(
        report,
        "avoid_list",
        [],
    ) or []

    if watch_list:

        print(
            "WATCH LIST:"
        )

        print(
            ", ".join(
                watch_list
            )
        )

        print()

    if avoid_list:

        print(
            "AVOID / REVIEW LIST:"
        )

        print(
            ", ".join(
                avoid_list
            )
        )

        print()

def main():

    parser = argparse.ArgumentParser(
        description=(
            "Baby Investor "
            "Batch Nemotron Pipeline"
        )
    )

    parser.add_argument(
        "profile",
        nargs="?",
        default="unusual-volume",
    )

    parser.add_argument(
        "--scan-file",
        default=None,
    )

    parser.add_argument(
        "--top",
        type=int,
        default=50,
    )

    parser.add_argument(
        "--committee",
        type=int,
        default=20,
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=10,
    )

    parser.add_argument(
        "--workers",
        type=int,
        default=6,
        help=(
            "Concurrent deterministic "
            "research workers."
        ),
    )

    parser.add_argument(
        "--nemotron-workers",
        type=int,
        default=2,
        help=(
            "Concurrent Nemotron "
            "batch requests."
        ),
    )

    parser.add_argument(
        "--no-cache",
        action="store_true",
    )

    args = parser.parse_args()

    scan_file = (
        args.scan_file
        or find_latest_scan(
            args.profile
        )
    )

    print(
        "Using scan:",
        scan_file,
    )

    pipeline = (
        InvestmentCommitteePipeline(

            use_cache=(
                not args.no_cache
            ),

            research_workers=(
                args.workers
            ),

            nemotron_workers=(
                args.nemotron_workers
            ),

            batch_size=(
                args.batch_size
            ),
        )
    )

    report = pipeline.run(

        scan_file=scan_file,

        top_n=args.top,

        committee_n=(
            args.committee
        ),
    )

    print_report(
        report
    )


if __name__ == "__main__":
    main()