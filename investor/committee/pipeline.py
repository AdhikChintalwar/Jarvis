from __future__ import annotations

import json
import time

from concurrent.futures import (
    ThreadPoolExecutor,
    as_completed,
)

from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from investor import StockAnalyzer

from investor.committee.analyst import (
    NemotronAnalyst,
)

from investor.committee.committee import (
    NemotronInvestmentCommittee,
)

from investor.committee.critic import (
    NemotronCritic,
)

from investor.committee.evidence_builder import (
    EvidenceBuilder,
)

from investor.committee.models import (
    CandidateIntelligence,
    CommitteeReport,
)

from investor.committee.nemotron_client import (
    NemotronClient,
)


class InvestmentCommitteePipeline:

    def __init__(
        self,
        use_cache: bool = True,
        research_workers: int = 6,
        nemotron_workers: int = 2,
        batch_size: int = 10,
    ):

        self.use_cache = use_cache

        self.research_workers = max(
            1,
            research_workers,
        )

        self.nemotron_workers = max(
            1,
            nemotron_workers,
        )

        self.batch_size = max(
            1,
            batch_size,
        )

        self.evidence_builder = (
            EvidenceBuilder()
        )

        self.nemotron = NemotronClient(
            use_cache=use_cache
        )

        self.analyst = NemotronAnalyst(
            self.nemotron
        )

        self.critic = NemotronCritic(
            self.nemotron
        )

        self.committee = (
            NemotronInvestmentCommittee(
                self.nemotron
            )
        )

        self.output_dir = Path(
            "data/investment_committee"
        )

        self.output_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

    def run(
        self,
        scan_file: str,
        top_n: int = 50,
        committee_n: int = 20,
    ) -> CommitteeReport:

        started = time.time()

        scan_path = Path(
            scan_file
        )

        scan_data = json.loads(
            scan_path.read_text()
        )

        profile = scan_data.get(
            "profile",
            "unknown",
        )

        raw_candidates = (
            scan_data.get(
                "candidates",
                []
            )
            or []
        )[:top_n]

        candidates = [
            self._candidate_from_scan(
                item
            )
            for item
            in raw_candidates
        ]

        raw_by_symbol = {
            self._symbol(
                item
            ): item
            for item
            in raw_candidates
        }

        print()
        print("=" * 80)
        print(
            "BABY INVESTMENT INTELLIGENCE V2"
        )
        print("=" * 80)

        print(
            f"Profile: {profile}"
        )

        print(
            f"Candidates: {len(candidates)}"
        )

        print(
            f"Research workers: "
            f"{self.research_workers}"
        )

        print(
            f"Nemotron batch size: "
            f"{self.batch_size}"
        )

        print(
            f"Nemotron workers: "
            f"{self.nemotron_workers}"
        )

        #
        # STAGE 1
        #
        # Parallel deterministic research
        #

        print()
        print("=" * 80)
        print(
            "STAGE 1 — PARALLEL RESEARCH"
        )
        print("=" * 80)

        with ThreadPoolExecutor(
            max_workers=(
                self.research_workers
            )
        ) as executor:

            futures = {}

            for candidate in candidates:

                raw = raw_by_symbol.get(
                    candidate.symbol,
                    {},
                )

                future = executor.submit(
                    self._research_candidate,
                    candidate.symbol,
                    raw,
                )

                futures[
                    future
                ] = candidate

            completed = 0

            for future in as_completed(
                futures
            ):

                candidate = futures[
                    future
                ]

                completed += 1

                try:

                    evidence = (
                        future.result()
                    )

                    candidate.evidence = (
                        evidence
                    )

                    print(
                        f"[{completed}/"
                        f"{len(candidates)}] "
                        f"{candidate.symbol} "
                        f"research complete"
                    )

                except Exception as error:

                    candidate.error = (
                        f"Research failed: "
                        f"{error}"
                    )

                    print(
                        f"[{completed}/"
                        f"{len(candidates)}] "
                        f"{candidate.symbol} "
                        f"ERROR: {error}"
                    )

                self._save_progress(
                    profile,
                    scan_path,
                    candidates,
                    stage=(
                        "deterministic_research"
                    ),
                )

        research_ready = [
            candidate
            for candidate
            in candidates
            if (
                candidate.error is None
                and candidate.evidence
            )
        ]

        print()
        print(
            f"Research complete: "
            f"{len(research_ready)}/"
            f"{len(candidates)}"
        )

        #
        # STAGE 2
        #
        # Batch Nemotron analyst
        #

        print()
        print("=" * 80)
        print(
            "STAGE 2 — NEMOTRON BATCH ANALYST"
        )
        print("=" * 80)

        analyst_batches = self._chunks(
            research_ready,
            self.batch_size,
        )

        self._run_analyst_batches(
            analyst_batches,
            profile,
            scan_path,
            candidates,
        )

        #
        # Cheap gate before critic
        #

        critic_ready = []

        print()
        print("=" * 80)
        print(
            "STAGE 3 — ANALYST PRE-GATE"
        )
        print("=" * 80)

        for candidate in candidates:

            if candidate.error:
                continue

            analyst = candidate.analyst

            if analyst is None:

                candidate.error = (
                    "No analyst result."
                )

                continue

            reasons = []

            if analyst.decision in {
                "AVOID",
                "INSUFFICIENT_DATA",
            }:

                reasons.append(
                    f"Analyst decision: "
                    f"{analyst.decision}"
                )

            if (
                analyst.conviction
                < 35
            ):

                reasons.append(
                    "Analyst conviction <35"
                )

            if (
                analyst.evidence_quality
                < 40
            ):

                reasons.append(
                    "Evidence quality <40"
                )

            if reasons:

                candidate.gate_reasons.extend(
                    reasons
                )

                print(
                    f"{candidate.symbol}: "
                    f"PRE-GATE FAIL — "
                    f"{'; '.join(reasons)}"
                )

            else:

                critic_ready.append(
                    candidate
                )

                print(
                    f"{candidate.symbol}: "
                    f"critic eligible "
                    f"({analyst.decision}, "
                    f"{analyst.conviction:.0f})"
                )

        print()
        print(
            f"Critic candidates: "
            f"{len(critic_ready)}/"
            f"{len(research_ready)}"
        )

        #
        # STAGE 4
        #
        # Batch critic
        #

        print()
        print("=" * 80)
        print(
            "STAGE 4 — NEMOTRON BATCH CRITIC"
        )
        print("=" * 80)

        critic_batches = self._chunks(
            critic_ready,
            self.batch_size,
        )

        self._run_critic_batches(
            critic_batches,
            profile,
            scan_path,
            candidates,
        )

        #
        # STAGE 5
        #
        # Final deterministic gate / scoring
        #

        print()
        print("=" * 80)
        print(
            "STAGE 5 — FINAL GATE"
        )
        print("=" * 80)

        survivors = []

        for candidate in candidates:

            if candidate.error:
                continue

            if candidate.analyst is None:
                continue

            if candidate.critic is None:
                continue

            self._calculate_candidate_score(
                candidate
            )

            self._apply_final_gate(
                candidate
            )

            print(
                f"{candidate.symbol}: "
                f"score="
                f"{candidate.final_candidate_score:.1f} "
                f"| "
                f"{'PASS' if candidate.passed_gate else 'FAIL'}"
            )

            if candidate.passed_gate:

                survivors.append(
                    candidate
                )

        survivors.sort(
            key=lambda item:
                item.final_candidate_score,
            reverse=True,
        )

        finalists = survivors[
            :committee_n
        ]

        #
        # STAGE 6
        #
        # Final committee
        #

        print()
        print("=" * 80)
        print(
            "STAGE 6 — FINAL NEMOTRON COMMITTEE"
        )
        print("=" * 80)

        print(
            f"Survivors: "
            f"{len(survivors)}"
        )

        print(
            f"Committee finalists: "
            f"{len(finalists)}"
        )

        committee_result = {
            "market_summary": "",
            "committee_summary": "",
            "rankings": [],
            "avoid_list": [],
            "watch_list": [],
        }

        if finalists:

            committee_result = (
                self.committee.rank(
                    finalists
                )
            )

        report = CommitteeReport(

            profile=profile,

            source_scan=str(
                scan_path
            ),

            candidates_processed=len(
                candidates
            ),

            candidates_passed=len(
                survivors
            ),

            rankings=committee_result[
                "rankings"
            ],

            market_summary=committee_result[
                "market_summary"
            ],

            committee_summary=committee_result[
                "committee_summary"
            ],

            avoid_list=committee_result[
                "avoid_list"
            ],

            watch_list=committee_result[
                "watch_list"
            ],

            errors=[
                (
                    f"{candidate.symbol}: "
                    f"{candidate.error}"
                )
                for candidate
                in candidates
                if candidate.error
            ],
        )

        self._save_final(
            report,
            candidates,
        )

        elapsed = (
            time.time()
            - started
        )

        print()
        print(
            f"Total pipeline time: "
            f"{elapsed / 60:.1f} minutes"
        )

        return report

    def _research_candidate(
        self,
        symbol,
        raw_scan,
    ):

        #
        # Separate analyzer per worker.
        # Avoid sharing provider/session state.
        #

        analyzer = StockAnalyzer()

        last_error = None

        for attempt in range(
            1,
            4,
        ):

            try:

                report = analyzer.analyze(
                    symbol
                )

                scan_object = (
                    self._scan_object(
                        raw_scan
                    )
                )

                return (
                    self.evidence_builder
                    .build(
                        scan_object,
                        report,
                    )
                )

            except Exception as error:

                last_error = error

                if attempt < 3:

                    time.sleep(
                        attempt * 2
                    )

        raise RuntimeError(
            str(last_error)
        )

    def _run_analyst_batches(
        self,
        batches,
        profile,
        scan_path,
        all_candidates,
    ):

        if not batches:
            return

        print(
            f"Analyst requests required: "
            f"{len(batches)}"
        )

        with ThreadPoolExecutor(
            max_workers=min(
                self.nemotron_workers,
                len(batches),
            )
        ) as executor:

            futures = {}

            for batch_number, batch in (
                enumerate(
                    batches,
                    start=1,
                )
            ):

                future = executor.submit(
                    self._analyst_batch_resilient,
                    batch,
                )

                futures[
                    future
                ] = (
                    batch_number,
                    batch,
                )

            for future in as_completed(
                futures
            ):

                (
                    batch_number,
                    batch,
                ) = futures[
                    future
                ]

                symbols = [
                    item.symbol
                    for item
                    in batch
                ]

                try:

                    results = (
                        future.result()
                    )

                    for candidate in batch:

                        result = results.get(
                            candidate.symbol
                        )

                        if result is None:

                            candidate.error = (
                                "Analyst omitted "
                                f"{candidate.symbol}"
                            )

                            continue

                        candidate.analyst = result

                    print(
                        f"Analyst batch "
                        f"{batch_number} complete: "
                        f"{', '.join(symbols)}"
                    )

                except Exception as error:

                    for candidate in batch:

                        if (
                            candidate.analyst
                            is None
                        ):

                            candidate.error = (
                                "Analyst failed: "
                                f"{error}"
                            )

                    print(
                        f"Analyst batch "
                        f"{batch_number} ERROR: "
                        f"{error}"
                    )

                self._save_progress(
                    profile,
                    scan_path,
                    all_candidates,
                    stage=(
                        "batch_analyst"
                    ),
                )

    def _analyst_batch_resilient(
    self,
    batch,
    ):

        payload = [
            {
                "symbol": candidate.symbol,
                "evidence": candidate.evidence,
            }
            for candidate in batch
        ]

        try:

            results = (
                self.analyst
                .analyze_batch(
                    payload
                )
            )

        except Exception:

            #
            # Complete request failure.
            # Split the batch immediately.
            #

            if len(batch) == 1:
                raise

            midpoint = max(
                1,
                len(batch) // 2,
            )

            print(
                "[Analyst fallback] "
                f"Splitting batch of {len(batch)} "
                f"into {midpoint} + "
                f"{len(batch) - midpoint}"
            )

            left = (
                self._analyst_batch_resilient(
                    batch[:midpoint]
                )
            )

            right = (
                self._analyst_batch_resilient(
                    batch[midpoint:]
                )
            )

            return {
                **left,
                **right,
            }

        #
        # Request succeeded, but Nemotron may
        # have returned only some candidates.
        #

        missing_candidates = [
            candidate
            for candidate in batch
            if candidate.symbol
            not in results
        ]

        if not missing_candidates:

            return results

        print(
            "[Analyst recovery] "
            f"Recovered "
            f"{len(results)}/{len(batch)}. "
            "Retrying only: "
            + ", ".join(
                candidate.symbol
                for candidate
                in missing_candidates
            )
        )

        #
        # If absolutely nothing was recovered,
        # divide the whole batch.
        #

        if (
            len(missing_candidates)
            == len(batch)
        ):

            if len(batch) == 1:

                raise RuntimeError(
                    "Nemotron returned no usable "
                    f"analyst result for "
                    f"{batch[0].symbol}"
                )

            midpoint = max(
                1,
                len(batch) // 2,
            )

            left = (
                self._analyst_batch_resilient(
                    batch[:midpoint]
                )
            )

            right = (
                self._analyst_batch_resilient(
                    batch[midpoint:]
                )
            )

            return {
                **left,
                **right,
            }

        #
        # Preserve successful results and
        # retry only missing stocks.
        #

        recovered_missing = (
            self._analyst_batch_resilient(
                missing_candidates
            )
        )

        return {
            **results,
            **recovered_missing,
        }

    def _run_critic_batches(
        self,
        batches,
        profile,
        scan_path,
        all_candidates,
    ):

        if not batches:
            return

        print(
            f"Critic requests required: "
            f"{len(batches)}"
        )

        with ThreadPoolExecutor(
            max_workers=min(
                self.nemotron_workers,
                len(batches),
            )
        ) as executor:

            futures = {}

            for batch_number, batch in (
                enumerate(
                    batches,
                    start=1,
                )
            ):

                future = executor.submit(
                    self._critic_batch_resilient,
                    batch,
                )

                futures[
                    future
                ] = (
                    batch_number,
                    batch,
                )

            for future in as_completed(
                futures
            ):

                (
                    batch_number,
                    batch,
                ) = futures[
                    future
                ]

                symbols = [
                    item.symbol
                    for item
                    in batch
                ]

                try:

                    results = (
                        future.result()
                    )

                    for candidate in batch:

                        result = results.get(
                            candidate.symbol
                        )

                        if result is None:

                            candidate.error = (
                                "Critic omitted "
                                f"{candidate.symbol}"
                            )

                            continue

                        candidate.critic = result

                    print(
                        f"Critic batch "
                        f"{batch_number} complete: "
                        f"{', '.join(symbols)}"
                    )

                except Exception as error:

                    for candidate in batch:

                        if (
                            candidate.critic
                            is None
                        ):

                            candidate.error = (
                                "Critic failed: "
                                f"{error}"
                            )

                    print(
                        f"Critic batch "
                        f"{batch_number} ERROR: "
                        f"{error}"
                    )

                self._save_progress(
                    profile,
                    scan_path,
                    all_candidates,
                    stage=(
                        "batch_critic"
                    ),
                )

    def _critic_batch_resilient(
        self,
        batch,
    ):

        payload = [
            {
                "symbol": candidate.symbol,

                "evidence":
                    candidate.evidence,

                "analyst":
                    candidate
                    .analyst
                    .to_dict(),
            }
            for candidate in batch
        ]

        try:

            results = (
                self.critic
                .critique_batch(
                    payload
                )
            )

        except Exception:

            if len(batch) == 1:
                raise

            midpoint = max(
                1,
                len(batch) // 2,
            )

            left = (
                self._critic_batch_resilient(
                    batch[:midpoint]
                )
            )

            right = (
                self._critic_batch_resilient(
                    batch[midpoint:]
                )
            )

            return {
                **left,
                **right,
            }

        missing_candidates = [
            candidate
            for candidate in batch
            if candidate.symbol
            not in results
        ]

        if not missing_candidates:
            return results

        print(
            "[Critic recovery] "
            f"Recovered "
            f"{len(results)}/{len(batch)}. "
            "Retrying only: "
            + ", ".join(
                candidate.symbol
                for candidate
                in missing_candidates
            )
        )

        if (
            len(missing_candidates)
            == len(batch)
        ):

            if len(batch) == 1:

                raise RuntimeError(
                    "Nemotron returned no usable "
                    f"critic result for "
                    f"{batch[0].symbol}"
                )

            midpoint = max(
                1,
                len(batch) // 2,
            )

            left = (
                self._critic_batch_resilient(
                    batch[:midpoint]
                )
            )

            right = (
                self._critic_batch_resilient(
                    batch[midpoint:]
                )
            )

            return {
                **left,
                **right,
            }

        recovered_missing = (
            self._critic_batch_resilient(
                missing_candidates
            )
        )

        return {
            **results,
            **recovered_missing,
        }

    def _apply_final_gate(
        self,
        candidate,
    ):

        reasons = list(
            candidate.gate_reasons
        )

        analyst = (
            candidate.analyst
        )

        critic = (
            candidate.critic
        )

        if analyst is None:

            reasons.append(
                "Missing analyst"
            )

        if critic is None:

            reasons.append(
                "Missing critic"
            )

        if analyst:

            if (
                analyst.evidence_quality
                < 45
            ):

                reasons.append(
                    "Evidence quality below 45"
                )

            if analyst.decision in {
                "AVOID",
                "INSUFFICIENT_DATA",
            }:

                reasons.append(
                    "Analyst veto"
                )

        if critic:

            if (
                critic.adjusted_conviction
                < 35
            ):

                reasons.append(
                    "Critic conviction below 35"
                )

            # V2.3 hardened adversarial gate.
            if (
                not critic.thesis_survives
                and critic.adjusted_conviction < 55
            ):

                reasons.append(
                    "Critic rejected thesis and "
                    "adjusted conviction is below 55"
                )

        candidate.gate_reasons = list(
            dict.fromkeys(
                reasons
            )
        )

        candidate.passed_gate = (
            len(
                candidate.gate_reasons
            )
            == 0
        )

    def _calculate_candidate_score(
        self,
        candidate,
    ):

        analyst = (
            candidate.analyst
        )

        critic = (
            candidate.critic
        )

        analyst_conviction = (
            analyst.conviction
            if analyst
            else 0
        )

        critic_conviction = (
            critic.adjusted_conviction
            if critic
            else 0
        )

        evidence_quality = (
            analyst.evidence_quality
            if analyst
            else 0
        )

        score = (
            candidate.scanner_score
            * 0.15

            + candidate.flow_score
            * 0.15

            + analyst_conviction
            * 0.30

            + critic_conviction
            * 0.30

            + evidence_quality
            * 0.10
        )

        if (
            critic
            and not critic.thesis_survives
        ):

            score -= 15

        candidate.final_candidate_score = round(
            max(
                0,
                min(
                    100,
                    score,
                ),
            ),
            1,
        )

    def _candidate_from_scan(
        self,
        raw,
    ):

        return CandidateIntelligence(

            symbol=self._symbol(
                raw
            ),

            scanner_score=self._first_number(
                raw,
                [
                    "opportunity_score",
                    "score",
                    "scanner_score",
                ],
            ),

            flow_score=self._first_number(
                raw,
                [
                    "flow_score",
                ],
            ),
        )

    def _scan_object(
        self,
        raw,
    ):

        data = dict(
            raw
        )

        aliases = {
            "symbol": self._symbol(
                raw
            ),

            "opportunity_score":
                self._first_number(
                    raw,
                    [
                        "opportunity_score",
                        "score",
                        "scanner_score",
                    ],
                ),

            "flow_score":
                self._first_number(
                    raw,
                    [
                        "flow_score",
                    ],
                ),
        }

        for key, value in (
            aliases.items()
        ):

            if key not in data:
                data[key] = value

        defaults = {
            "flow_type": "UNKNOWN",
            "relative_volume": None,
            "volume_zscore": None,
            "daily_change_pct": None,
            "gap_pct": None,
            "close_location_pct": None,
            "breakout_20d": False,
            "breakdown_20d": False,
            "flags": [],
        }

        for key, value in (
            defaults.items()
        ):

            data.setdefault(
                key,
                value,
            )

        return SimpleNamespace(
            **data
        )

    def _symbol(
        self,
        raw,
    ):

        return str(
            raw.get(
                "symbol",
                raw.get(
                    "ticker",
                    "",
                ),
            )
        ).upper()

    def _first_number(
        self,
        source,
        keys,
    ):

        for key in keys:

            value = source.get(
                key
            )

            if value is None:
                continue

            try:
                return float(
                    value
                )

            except Exception:
                continue

        return 0.0

    def _chunks(
        self,
        items,
        size,
    ):

        return [
            items[
                index:
                index + size
            ]
            for index
            in range(
                0,
                len(items),
                size,
            )
        ]

    def _save_progress(
        self,
        profile,
        scan_path,
        candidates,
        stage,
    ):

        path = (
            self.output_dir
            / f"{profile}_progress.json"
        )

        payload = {
            "source_scan": str(
                scan_path
            ),

            "stage": stage,

            "updated_at": (
                datetime.now()
                .isoformat()
            ),

            "candidates": [
                candidate.to_dict()
                for candidate
                in candidates
            ],
        }

        path.write_text(
            json.dumps(
                payload,
                indent=2,
                default=str,
            )
        )

    def _save_final(
        self,
        report,
        candidates,
    ):

        stamp = (
            datetime.now()
            .strftime(
                "%Y%m%d_%H%M%S"
            )
        )

        # V2.3 canonical report schema. Committee fields live
        # at the top level so consumers can always use
        # report["rankings"], report["market_summary"], etc.
        payload = report.to_dict()

        payload["schema_version"] = "2.3"

        payload["candidate_intelligence"] = [
            candidate.to_dict()
            for candidate
            in candidates
        ]

        path = (
            self.output_dir
            / (
                f"{report.profile}_"
                f"{stamp}.json"
            )
        )

        latest = (
            self.output_dir
            / (
                f"{report.profile}_"
                f"latest.json"
            )
        )

        serialized = json.dumps(
            payload,
            indent=2,
            default=str,
        )

        path.write_text(
            serialized
        )

        latest.write_text(
            serialized
        )

        print()
        print(
            "Final report:",
            path,
        )