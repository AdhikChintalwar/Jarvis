from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from investor import StockAnalyzer

from investor.scanner.batch_market_data import (
    BatchMarketData,
)

from investor.scanner.models import (
    DeepCandidate,
    ScanSummary,
)

from investor.scanner.opportunity_scorer import (
    OpportunityScorer,
)

from investor.scanner.quantitative_filter import (
    QuantitativeFilter,
)

from investor.scanner.scan_profiles import (
    get_profile,
)

from investor.scanner.universe import (
    USStockUniverse,
)


class MarketScanner:

    def __init__(
        self,
        batch_size: int = 100,
    ):

        self.universe = (
            USStockUniverse()
        )

        self.market_data = (
            BatchMarketData(
                batch_size=batch_size
            )
        )

        self.quant_filter = (
            QuantitativeFilter()
        )

        self.scorer = (
            OpportunityScorer()
        )

        self.output_dir = Path(
            "data/scans"
        )

        self.output_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

    def scan(
        self,
        profile_name: str,
        limit: int | None = None,
        top_n: int = 50,
        deep_n: int = 0,
    ) -> ScanSummary:

        profile = get_profile(
            profile_name
        )

        print()
        print("=" * 72)
        print(
            "BABY MARKET SCANNER"
        )
        print("=" * 72)

        print(
            "Profile:",
            profile.name.upper(),
        )

        print()
        print(
            "[1/5] Loading U.S. equity universe..."
        )

        stocks = (
            self.universe.load(
                limit=limit
            )
        )

        summary = ScanSummary(
            profile=profile.name,

            universe_count=len(
                stocks
            ),
        )

        print(
            f"Universe: "
            f"{len(stocks):,} symbols"
        )

        print()
        print(
            "[2/5] Downloading market data..."
        )

        batch = (
            self.market_data.download(
                stocks=stocks,
                period="1y",
                interval="1d",
            )
        )

        summary.market_data_count = (
            len(batch.data)
        )

        print()
        print(
            f"Market data available: "
            f"{len(batch.data):,}"
        )

        print(
            f"Failed/missing: "
            f"{len(batch.failures):,}"
        )

        print()
        print(
            "[3/5] Running eligibility "
            "and quantitative filters..."
        )

        stock_map = {
            stock.symbol: stock
            for stock
            in stocks
        }

        candidates = []

        eligible_count = 0

        for index, (
            symbol,
            history,
        ) in enumerate(
            batch.data.items(),
            start=1,
        ):

            stock = stock_map.get(
                symbol
            )

            if stock is None:
                continue

            try:

                metrics = (
                    self.quant_filter
                    .analyze(
                        stock=stock,

                        history=history,

                        profile=profile,
                    )
                )

                if metrics is None:
                    continue

                eligible_count += 1

                scored = (
                    self.scorer.score(
                        metrics=metrics,
                        profile=profile,
                    )
                )

                if (
                    scored.opportunity_score
                    < profile.min_score
                ):
                    continue

                candidates.append(
                    scored
                )

            except Exception as error:

                summary.errors.append(
                    f"{symbol}: {error}"
                )

            if (
                index % 500 == 0
            ):
                print(
                    f"Processed "
                    f"{index:,}/"
                    f"{len(batch.data):,}"
                )

        summary.eligibility_count = (
            eligible_count
        )

        candidates.sort(
            key=lambda item: (
                item.opportunity_score
            ),
            reverse=True,
        )

        candidates = (
            candidates[:top_n]
        )

        summary.candidates = (
            candidates
        )

        summary.quantitative_count = (
            len(candidates)
        )

        print()
        print(
            f"Passed basic eligibility: "
            f"{eligible_count:,}"
        )

        print(
            f"Final quantitative candidates: "
            f"{len(candidates):,}"
        )

        print()
        print(
            "[4/5] Quantitative ranking complete."
        )

        if deep_n > 0:

            print()
            print(
                f"Running deep Baby analysis "
                f"on top {deep_n}..."
            )

            summary.deep_candidates = (
                self._deep_analyze(
                    candidates[
                        :deep_n
                    ]
                )
            )

            summary.deep_analysis_count = (
                len(
                    summary.deep_candidates
                )
            )

        print()
        print(
            "[5/5] Saving scan..."
        )

        output = (
            self._save(
                summary
            )
        )

        print(
            "Saved:",
            output,
        )

        return summary

    def _deep_analyze(
        self,
        candidates,
    ):

        analyzer = (
            StockAnalyzer()
        )

        results = []

        for number, candidate in (
            enumerate(
                candidates,
                start=1,
            )
        ):

            print()
            print(
                f"Deep analysis "
                f"{number}/"
                f"{len(candidates)}: "
                f"{candidate.symbol}"
            )

            try:

                report = (
                    analyzer.analyze(
                        candidate.symbol
                    )
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

                quality = (
                    report[
                        "data_quality"
                    ]
                )

                risk = (
                    report["risk"]
                )

                sec = (
                    report["sec"]
                )

                technical = (
                    report[
                        "technical"
                    ]
                )

                thesis = (
                    report["thesis"]
                )

                results.append(
                    DeepCandidate(
                        symbol=(
                            candidate.symbol
                        ),

                        scan_score=(
                            candidate
                            .opportunity_score
                        ),

                        decision=(
                            thesis.decision
                        ),

                        stock_type=(
                            classification
                            .stock_type
                            .value
                        ),

                        trading_profile=(
                            classification
                            .trading_profile
                            .value
                        ),

                        financial_health=(
                            financial.score
                        ),

                        data_quality=(
                            quality.score
                        ),

                        risk=(
                            risk
                            .overall_risk
                            .value
                        ),

                        dilution_risk=(
                            sec
                            .dilution_risk
                        ),

                        price=(
                            technical.price
                        ),

                        rsi=(
                            technical.rsi_14
                        ),

                        relative_volume=(
                            technical
                            .relative_volume
                        ),

                        reasons=(
                            thesis.reasons
                        ),
                    )
                )

            except Exception as error:

                print(
                    "Deep analysis failed:",
                    candidate.symbol,
                    error,
                )

        return results

    def _save(
        self,
        summary,
    ):

        stamp = (
            datetime.now()
            .strftime(
                "%Y%m%d_%H%M%S"
            )
        )

        filename = (
            f"{summary.profile}_"
            f"{stamp}.json"
        )

        path = (
            self.output_dir
            / filename
        )

        path.write_text(
            json.dumps(
                summary.to_dict(),
                indent=2,
                default=str,
            )
        )

        latest = (
            self.output_dir
            / f"{summary.profile}_latest.json"
        )

        latest.write_text(
            json.dumps(
                summary.to_dict(),
                indent=2,
                default=str,
            )
        )

        return path