from __future__ import annotations

from typing import Any

from investor.committee.models import (
    CandidateIntelligence,
    CommitteeRanking,
)

from investor.committee.committee_guard import (
    FinalCommitteeGuard,
)
from investor.committee.deep_deliberation import DeepDeliberationEngine

from investor.integrity import (
    ClaimValidator,
    EvidenceRegistry,
    ReportValidator,
)


COMMITTEE_SYSTEM_PROMPT = """
You are Baby's FAST final investment-research synthesis layer.

Baby's deterministic engines already calculated the quantitative research
baseline, evidence authority, risk level, hard overrides, and decision ceiling.
Do not recalculate them and do not override them.

Use ONLY the supplied compact_evidence rows and deterministic_committee_guard.

Your task is intentionally narrow:
1. propose a research score for synthesis only;
2. propose a decision within the supplied maximum_decision;
3. write a few short evidence-grounded claims.

STRICT CLAIM CONSTRUCTION
- Every non-UNKNOWN claim must cite exact supplied evidence IDs.
- Prefer one evidence ID per claim.
- If a claim contains a number, copy the exact value from that evidence row.
- Do not introduce ratios, percentages, dollar values, dates, metrics, names,
  causes, competitors, insider activity, institutional activity, or estimates
  that are not present in the cited evidence row.
- Do not combine unrelated evidence into one sentence.
- Do not convert decimals into percentages. Copy the supplied numeric value
  exactly when using a number.
- If uncertain, emit UNKNOWN instead of guessing.
- Do not repeat facts already absent from compact_evidence.
- A hard-risk override cannot be cancelled by narrative judgment.

committee_score is research-attractiveness synthesis, not predicted return.
This output is research support, not an instruction to trade.

Maximum per stock:
- 1 strength claim
- 1 risk claim
- 1 rationale claim
- 1 UNKNOWN claim
Maximum 4 claims per stock.
Maximum 22 words per statement.

Allowed decisions:
TOP_CANDIDATE, CANDIDATE, WATCH, WAIT, AVOID

Allowed claim types:
FACT, CALCULATION, INFERENCE, UNKNOWN

Allowed categories:
STRENGTH, RISK, RATIONALE, ACTION, CATALYST, OTHER

Return ONLY valid JSON:
{
  "rankings": [
    {
      "symbol": "XYZ",
      "rank": 1,
      "committee_score": 70,
      "decision": "WATCH",
      "confidence": 70,
      "claims": [
        {
          "claim_id": "XYZ_1",
          "statement": "Unified risk level is VERY_HIGH.",
          "type": "FACT",
          "category": "RISK",
          "evidence_ids": ["unified_risk.risk_level"],
          "confidence": 95
        }
      ]
    }
  ]
}

No markdown. No prose outside JSON.
"""


COMMITTEE_DEEP_PROMPT = """
You are Baby's FINAL deep investment committee.
Use compact deterministic evidence, deterministic_committee_guard, and ONLY the
supported claims inside validated_deliberation. Think deeply and reconcile bull,
bear, contradictions, valuation, fundamentals, accounting/cash flow, events,
macro/market structure, and risk.

Never resurrect unsupported deliberation claims. Never override maximum_decision,
hard-risk overrides, evidence constraints, or missing data.
Every FACT/CALCULATION/INFERENCE must cite exact compact-evidence IDs.
Numerical statements must copy exact cited values. If unavailable, use UNKNOWN.
Actively consider disconfirming evidence.
committee_score is research attractiveness, not predicted return or an order.

Return ONLY Baby's ranking JSON schema. Maximum 5 claims/security.
No markdown or prose outside JSON.
"""


class NemotronInvestmentCommittee:

    COMPACT_ROOTS = (
        "financial_health",
        "accounting_quality",
        "valuation",
        "event_intelligence",
        "macro_regime",
        "advanced_market",
        "unified_risk",
        "liquidity_evidence",
        "primary_financial",
    )

    COMPACT_SUFFIXES = (
        ".score", ".confidence", ".coverage",
        ".evidence_confidence", ".evidence_coverage",
        ".confidence_adjusted_score",
        ".risk_score", ".risk_level",
        ".hard_overrides", ".position_risk_multiplier",
        ".regime", ".market_structure", ".breadth_regime",
        ".stock_relative_strength", ".sector_regime",
        ".participation_regime", ".volatility_state",
        ".profitability_state", ".fcf_state",
        ".revenue_growth_yoy.value", ".net_margin.value",
        ".operating_margin.value", ".free_cash_flow.value",
        ".operating_cash_flow.value", ".cash.value", ".debt.value",
    )

    def __init__(
        self,
        client,
    ):

        self.client = client

        self.evidence_registry = (
            EvidenceRegistry()
        )

        self.claim_validator = (
            ClaimValidator()
        )

        self.report_validator = (
            ReportValidator()
        )

        self.committee_guard = (
            FinalCommitteeGuard()
        )
        self.deep_deliberation = DeepDeliberationEngine(client)

    @staticmethod
    def _sanitize_final_claims(raw_claims):
        """Normalize untrusted LLM claims before deterministic validation."""
        rejected = []
        if raw_claims is None:
            return [], rejected
        if isinstance(raw_claims, dict):
            raw_claims = [raw_claims]
        elif isinstance(raw_claims, str):
            return [], [{"raw": raw_claims, "reason": "final_claims_container_was_string"}]
        elif not isinstance(raw_claims, list):
            return [], [{"raw": repr(raw_claims), "reason": "final_claims_container_invalid_type"}]

        safe = []
        for index, item in enumerate(raw_claims):
            if isinstance(item, dict):
                safe.append(item)
            else:
                rejected.append({
                    "raw": item if isinstance(item, str) else repr(item),
                    "index": index,
                    "reason": "final_claim_member_not_object",
                })
        return safe, rejected

    def rank(
        self,
        candidates: list[
            CandidateIntelligence
        ],
        deep_review: bool = True,
    ) -> dict:

        if not candidates:

            return {
                "market_summary": "",
                "committee_summary":
                    "No candidates passed the final gate.",
                "rankings": [],
                "avoid_list": [],
                "watch_list": [],
            }

        payload_candidates = []

        candidate_lookup = {}

        registry_lookup = {}
        guard_lookup = {}

        for candidate in candidates:

            symbol = (
                candidate.symbol
                .upper()
                .strip()
            )

            candidate_lookup[
                symbol
            ] = candidate

            generated_at = None

            if isinstance(
                candidate.evidence,
                dict,
            ):

                generated_at = (
                    candidate.evidence.get(
                        "generated_at"
                    )
                )

            registry = (
                self.evidence_registry.build(
                    candidate.evidence,
                    generated_at=
                        generated_at,
                )
            )

            registry_lookup[
                symbol
            ] = registry

            guard = self.committee_guard.evaluate(
                candidate.evidence
            )
            guard_lookup[symbol] = guard

            payload_candidates.append(
                self._candidate_payload(
                    candidate,
                    registry,
                    guard,
                )
            )

        deliberations = {}
        deliberation_status = {
            "status": "NOT_REQUESTED",
            "repair_attempted": False,
        }

        if deep_review:
            deliberations, deliberation_status = self._run_deep_deliberation(
                payload_candidates,
                registry_lookup,
            )
            for item in payload_candidates:
                symbol = str(item.get("symbol", "")).upper().strip()
                item["validated_deliberation"] = deliberations.get(
                    symbol,
                    {
                        "status": "UNAVAILABLE",
                        "claims": [],
                        "unsupported_claims": [],
                        "integrity_score": 0.0,
                        "unresolved_questions": [],
                    },
                )

        payload = {
            "candidate_count": len(payload_candidates),
            "candidates": payload_candidates,
        }

        committee_unavailable_error = None
        if (
            deep_review
            and deliberation_status.get("status")
                == "DEEP_DELIBERATION_UNAVAILABLE"
        ):
            print(
                "[Committee] Deep deliberation unavailable. "
                "Skipping final AI committee and using deterministic governed "
                "fallback."
            )
            result = self._deterministic_provider_fallback(payload_candidates)
            committee_unavailable_error = "DEEP_DELIBERATION_UNAVAILABLE"
        else:
            try:
                result = self._run_committee_resilient(
                    payload=payload,
                    candidate_count=len(candidates),
                    deep_review=deep_review,
                )
            except Exception as error:
                committee_unavailable_error = str(error)
                print(
                    "[Committee] Deep committee failed after recovery/retries: "
                    f"{type(error).__name__}: {error}"
                )
                print(
                    "[Committee] Using deterministic governed fallback; "
                    "no AI conclusion will be invented."
                )
                result = self._deterministic_provider_fallback(
                    payload_candidates
                )

        deterministic_only = bool(
            isinstance(result, dict)
            and result.get("_deterministic_only")
        )

        raw_rankings = (
            result.get(
                "rankings",
                [],
            )
            or []
        )

        schema_diag = (
            result.get("_schema_diagnostics", {})
            if isinstance(result, dict)
            else {}
        )

        if not raw_rankings:
            print(
                "[Committee] Deep committee schema remained invalid. "
                "Using deterministic governed fallback; no AI conclusion "
                "will be invented."
            )
            result = self._deterministic_provider_fallback(
                payload_candidates
            )
            result["_schema_diagnostics"] = {
                **schema_diag,
                "valid": False,
                "fallback": "DETERMINISTIC_ONLY",
            }
            deterministic_only = True
            raw_rankings = result.get("rankings", []) or []
            committee_unavailable_error = (
                "DEEP_COMMITTEE_SCHEMA_INVALID"
            )

        validated_rankings = []

        for raw in raw_rankings:

            if not isinstance(
                raw,
                dict,
            ):
                continue

            symbol = str(
                raw.get(
                    "symbol",
                    "",
                )
            ).upper().strip()

            if (
                not symbol
                or symbol
                not in candidate_lookup
            ):
                continue

            registry = (
                registry_lookup[
                    symbol
                ]
            )

            raw_claims = raw.get("claims", [])
            safe_claims, malformed_claims = (
                self._sanitize_final_claims(raw_claims)
            )

            integrity = (
                self.claim_validator.validate(
                    safe_claims,
                    registry,
                )
            )

            safe_fields = (
                self.report_validator
                .build_safe_fields(
                    integrity
                )
            )

            confidence = (
                self._number(
                    raw.get(
                        "confidence",
                        0,
                    )
                )
            )

            unsupported_count = (
                len(integrity.unsupported_claims)
                + len(malformed_claims)
            )

            if unsupported_count:

                confidence -= min(
                    30.0,
                    unsupported_count
                    * 5.0,
                )

            confidence = max(
                0.0,
                min(
                    100.0,
                    confidence,
                ),
            )

            decision = str(
                raw.get(
                    "decision",
                    "WATCH",
                )
            ).upper().strip()

            allowed_decisions = {
                "TOP_CANDIDATE",
                "CANDIDATE",
                "WATCH",
                "WAIT",
                "AVOID",
            }

            if (
                decision
                not in allowed_decisions
            ):

                decision = "WATCH"

            # V2.3 integrity consequences.

            if (
                integrity.integrity_score
                < 60.0
            ):

                decision = (
                    "REVIEW_REQUIRED"
                )

                confidence = min(
                    confidence,
                    30.0,
                )

            elif (
                integrity.integrity_score
                < 80.0
            ):

                confidence = min(
                    confidence,
                    60.0,
                )

            guard = guard_lookup[symbol]

            governed = self.committee_guard.apply(
                llm_score=self._number(
                    raw.get("committee_score", 0)
                ),
                llm_decision=decision,
                llm_confidence=confidence,
                integrity_score=integrity.integrity_score,
                guard=guard,
                deterministic_only=deterministic_only,
            )

            if deterministic_only:
                governed["decision"] = (
                    "WATCH"
                    if guard.maximum_decision in {"WATCH", "WAIT", "AVOID"}
                    else "RESEARCH_ONLY"
                )

            # Integrity failure is stricter than the ordinary decision ladder.
            if integrity.integrity_score < 60.0 and not deterministic_only:
                governed["decision"] = "REVIEW_REQUIRED"
                governed["confidence"] = min(
                    governed["confidence"], 30.0
                )

            ranking = CommitteeRanking(
                symbol=symbol,

                rank=max(
                    1,
                    int(
                        self._number(
                            raw.get(
                                "rank",
                                999,
                            )
                        )
                    ),
                ),

                committee_score=governed["final_score"],

                deterministic_score=guard.deterministic_score,
                llm_score=governed["llm_score"],
                llm_weight=governed.get("llm_weight", 0.0),
                evidence_authority=guard.evidence_authority,
                module_coverage=guard.module_coverage,
                governance_status=guard.governance_status,
                maximum_decision=guard.maximum_decision,
                governance_constraints=guard.constraints,
                deterministic_modules=guard.module_scores,

                decision=governed["decision"],

                confidence=governed["confidence"],

                why_ranked_here=
                    safe_fields[
                        "why_ranked_here"
                    ],

                strongest_strength=
                    safe_fields[
                        "strongest_strength"
                    ],

                biggest_risk=
                    safe_fields[
                        "biggest_risk"
                    ],

                preferred_action=
                    safe_fields[
                        "preferred_action"
                    ],

                integrity_passed=
                    integrity.passed,

                integrity_score=
                    integrity.integrity_score,

                supported_claims=[
                    claim.to_dict()

                    for claim
                    in integrity
                    .supported_claims
                ],

                unsupported_claims=(
                    [
                        claim.to_dict()
                        for claim
                        in integrity.unsupported_claims
                    ]
                    + malformed_claims
                ),

                unknowns=
                    safe_fields[
                        "unknowns"
                    ],

                evidence_used=
                    integrity.evidence_used,

                raw=raw,
            )

            validated_rankings.append(
                ranking.to_dict()
            )

        validated_rankings = (
            self._normalize_rankings(
                validated_rankings
            )
        )

        market_summary = (
            self._build_market_summary(
                validated_rankings
            )
        )

        committee_summary = (
            self._build_committee_summary(
                validated_rankings
            )
        )

        avoid_list = []

        watch_list = []

        for ranking in (
            validated_rankings
        ):

            symbol = ranking[
                "symbol"
            ]

            decision = ranking[
                "decision"
            ]

            if decision in {
                "AVOID",
                "REVIEW_REQUIRED",
            }:

                avoid_list.append(
                    symbol
                )

            elif decision in {
                "WATCH",
                "WAIT",
            }:

                watch_list.append(
                    symbol
                )

        if committee_unavailable_error:
            for ranking in validated_rankings:
                ranking["provider_status"] = "DEEP_COMMITTEE_UNAVAILABLE"
                ranking["provider_error"] = committee_unavailable_error
                ranking["confidence"] = 0.0

        return {
            "market_summary": market_summary,
            "committee_summary": committee_summary,
            "rankings": validated_rankings,
            "avoid_list": avoid_list,
            "watch_list": watch_list,
            "provider_status": (
                "DEEP_COMMITTEE_SCHEMA_INVALID"
                if committee_unavailable_error == "DEEP_COMMITTEE_SCHEMA_INVALID"
                else (
                    "DEEP_COMMITTEE_UNAVAILABLE"
                    if committee_unavailable_error
                    else "OK"
                )
            ),
            "committee_schema": (
                result.get("_schema_diagnostics", {})
                if isinstance(result, dict)
                else {}
            ),
            "deterministic_only": deterministic_only,
            "llm_weight": 0.0 if deterministic_only else None,
            "deliberation_status": deliberation_status,
            # Audit-only: validated first-stage deep deliberation. This does
            # not alter committee scoring or governance.
            "deep_deliberation": deliberations,
        }

    def _run_deep_deliberation(self, payload_candidates, registry_lookup):
        deliberation_provider_status = "OK"
        repair_attempted = False
        try:
            raw_lookup = self.deep_deliberation.deliberate(payload_candidates)
        except Exception as error:
            print(
                "[Deliberation] Primary deep pass failed: "
                f"{type(error).__name__}: {error}"
            )
            print("[Deliberation] One JSON/schema recovery pass — thinking=ON")
            repair_attempted = True
            recovery_prompt = """
You are a JSON recovery layer for Baby's deep investment deliberation.
Re-run the deliberation from ONLY the supplied candidate evidence because the
previous response was truncated or malformed.

Return ONLY valid compact JSON:
{"deliberations":[{"symbol":"XYZ","bull_score":50,"bear_score":50,
"synthesis_score":50,"confidence":50,"bull_claims":[],"bear_claims":[],
"contradictions":[],"unresolved_questions":[]}]}

Every bull_claims/bear_claims/contradictions member MUST be an object with:
claim_id, statement, type, category, evidence_ids, confidence.
Use exact supplied evidence IDs and exact numeric values. No forecasts, targets,
causes, competitors, management intentions, market share, TAM, or invented facts.
Maximum 2 bull claims, 2 bear claims, 1 contradiction, 3 unresolved questions
per security. Maximum 16 words per claim. Include every supplied symbol.
"""
            try:
                recovered = self.client.reason_json(
                    system_prompt=recovery_prompt,
                    payload={"candidates": payload_candidates},
                    task_name="investment_deliberation_recovery_v4_5_8",
                    temperature=0.0,
                    max_tokens=max(9000, len(payload_candidates) * 2500),
                    retries=1,
                    enable_thinking=True,
                )
                rows = recovered.get("deliberations", []) if isinstance(recovered, dict) else []
                if not (
                    isinstance(rows, list)
                    and rows
                    and all(isinstance(x, dict) and x.get("symbol") for x in rows)
                ):
                    raise ValueError("Recovery returned no usable deliberations")
                raw_lookup = {
                    str(x.get("symbol", "")).upper().strip(): x
                    for x in rows
                    if isinstance(x, dict) and x.get("symbol")
                }
                deliberation_provider_status = "RECOVERED"
            except Exception as recovery_error:
                print(
                    "[Deliberation] Recovery unavailable/invalid. "
                    "Continuing deterministic-only; no deliberation conclusion "
                    "will be invented."
                )
                return {}, {
                    "status": "DEEP_DELIBERATION_UNAVAILABLE",
                    "primary_error": str(error),
                    "recovery_error": str(recovery_error),
                    "repair_attempted": True,
                }

        validated = {}
        for symbol, raw in raw_lookup.items():
            registry = registry_lookup.get(symbol, {})
            claims = []
            malformed_claims = []

            for key in (
                "bull_claims",
                "bear_claims",
                "contradictions",
            ):
                section = raw.get(key, []) or []

                # Nemotron may occasionally return a prose string instead
                # of the requested list[dict]. Never send malformed output
                # into ClaimValidator.
                if isinstance(section, dict):
                    section = [section]
                elif isinstance(section, str):
                    malformed_claims.append(
                        {
                            "section": key,
                            "raw": section,
                            "reason": "string_instead_of_claim_list",
                        }
                    )
                    section = []
                elif not isinstance(section, list):
                    malformed_claims.append(
                        {
                            "section": key,
                            "raw": repr(section),
                            "reason": "invalid_claim_container",
                        }
                    )
                    section = []

                for claim in section:
                    if isinstance(claim, dict):
                        claims.append(claim)
                    else:
                        malformed_claims.append(
                            {
                                "section": key,
                                "raw": str(claim),
                                "reason": "non_object_claim",
                            }
                        )

            integrity = self.claim_validator.validate(claims, registry)
            supported_ids = {
                r.claim_id
                for r in integrity.supported_claims
            }
            unknown_ids = {
                r.claim_id
                for r in integrity.unknown_claims
            }
            supported = [
                c for c in claims
                if str(c.get("claim_id", "")) in supported_ids
            ]
            unsupported = [
                c for c in claims
                if str(c.get("claim_id", "")) not in supported_ids
            ]

            # Malformed model output is retained for auditability but is
            # never treated as evidence or passed to the final committee.
            unsupported.extend(malformed_claims)

            unknown_claims = [
                c for c in claims
                if str(c.get("claim_id", "")) in unknown_ids
            ]
            total_attempted = (
                len(integrity.supported_claims)
                + len(integrity.unsupported_claims)
                + len(integrity.unknown_claims)
                + len(malformed_claims)
            )
            accepted_count = len(integrity.supported_claims)
            schema_integrity = (
                100.0 * (total_attempted - len(malformed_claims)) / total_attempted
                if total_attempted else 100.0
            )
            effective_integrity = (
                100.0 * accepted_count / total_attempted
                if total_attempted else 100.0
            )

            validated[symbol] = {
                "status": (
                    "PASS" if effective_integrity >= 80.0
                    else "LIMITED"
                ),
                "bull_score": raw.get("bull_score"),
                "bear_score": raw.get("bear_score"),
                "synthesis_score": raw.get("synthesis_score"),
                "confidence": raw.get("confidence"),
                "claims": supported,
                "unsupported_claims": unsupported,
                "integrity_score": integrity.integrity_score,
                "schema_integrity": round(schema_integrity, 2),
                "effective_integrity": round(effective_integrity, 2),
                "accepted_claim_count": accepted_count,
                "rejected_claim_count": len(unsupported),
                "unknown_claims": unknown_claims,
                "unresolved_questions": raw.get("unresolved_questions", []) or [],
            }
        return validated, {
            "status": (
                "DEEP_DELIBERATION_RECOVERED"
                if deliberation_provider_status == "RECOVERED"
                else "DEEP_DELIBERATION_OK"
            ),
            "repair_attempted": repair_attempted,
        }

    def _deterministic_provider_fallback(self, payload_candidates) -> dict:
        rankings = []
        ordered = sorted(
            payload_candidates,
            key=lambda x: float(
                x.get("deterministic_committee_guard", {})
                 .get("deterministic_score", 50.0)
            ),
            reverse=True,
        )
        for rank, item in enumerate(ordered, start=1):
            guard = item.get("deterministic_committee_guard", {})
            baseline = float(guard.get("deterministic_score", 50.0))
            rankings.append({
                "symbol": str(item.get("symbol","")).upper().strip(),
                "rank": rank,
                "committee_score": baseline,
                "decision": str(guard.get("maximum_decision","WATCH")),
                "confidence": 0.0,
                "claims": [],
            })
        return {
            "rankings": rankings,
            "_deterministic_only": True,
        }

    @staticmethod
    def _committee_schema_diagnostics(result) -> dict:
        keys = sorted(result.keys()) if isinstance(result, dict) else []
        rankings = result.get("rankings") if isinstance(result, dict) else None
        valid_rows = (
            isinstance(rankings, list)
            and bool(rankings)
            and all(
                isinstance(row, dict)
                and bool(str(row.get("symbol", "")).strip())
                for row in rankings
            )
        )
        return {
            "valid": bool(valid_rows),
            "raw_response_type": type(result).__name__,
            "raw_response_keys": keys,
            "ranking_count": len(rankings) if isinstance(rankings, list) else 0,
            "reason": (
                None if valid_rows
                else "missing, empty, or malformed rankings array"
            ),
        }

    def _run_committee_resilient(
        self,
        payload: dict,
        candidate_count: int,
        deep_review: bool = False,
    ) -> dict:

        if deep_review:
            print("[Committee] Explicit deep review — thinking=ON")
            result = self.client.reason_json(
                system_prompt=COMMITTEE_DEEP_PROMPT,
                payload=payload,
                task_name="investment_committee_deep_v4_5",
                temperature=0.03,
                max_tokens=max(5000, candidate_count * 1300),
                retries=1,
                enable_thinking=True,
            )

            diag = self._committee_schema_diagnostics(result)
            if diag["valid"]:
                result["_schema_diagnostics"] = {
                    **diag,
                    "repair_attempted": False,
                    "repair_success": False,
                }
                return result

            print(
                "[Committee schema invalid] "
                f"keys={diag['raw_response_keys']} "
                f"rankings={diag['ranking_count']} "
                f"reason={diag['reason']}"
            )
            print("[Committee] One deep schema-repair pass — thinking=ON")

            repair_payload = {
                "instruction": (
                    "Reformat the previous committee output into the exact "
                    "required committee schema. Do not add new facts, evidence, "
                    "forecasts, targets, causes, or conclusions. Preserve only "
                    "content already present in the previous output and the "
                    "provided candidate symbols. Return a non-empty 'rankings' "
                    "array with one object per candidate."
                ),
                "candidate_symbols": [
                    str(c.get("symbol", "")).upper()
                    for c in payload.get("candidates", [])
                    if isinstance(c, dict) and c.get("symbol")
                ],
                "previous_output": result,
                "required_top_level": {
                    "rankings": [
                        {
                            "symbol": "TICKER",
                            "rank": 1,
                            "committee_score": 50,
                            "decision": "WATCH",
                            "confidence": 50,
                            "claims": [],
                        }
                    ]
                },
            }

            repaired = self.client.reason_json(
                system_prompt=COMMITTEE_DEEP_PROMPT,
                payload=repair_payload,
                task_name="investment_committee_schema_repair_v4_5_5",
                temperature=0.0,
                max_tokens=max(3500, candidate_count * 900),
                retries=1,
                enable_thinking=True,
            )
            repaired_diag = self._committee_schema_diagnostics(repaired)
            repaired["_schema_diagnostics"] = {
                **repaired_diag,
                "repair_attempted": True,
                "repair_success": bool(repaired_diag["valid"]),
                "original_keys": diag["raw_response_keys"],
                "original_ranking_count": diag["ranking_count"],
            }
            return repaired

        print("[Committee] Fast evidence synthesis — thinking=OFF")
        try:
            return self.client.reason_json(
                system_prompt=COMMITTEE_SYSTEM_PROMPT,
                payload=payload,
                task_name="investment_committee_fast_v4_4_1",
                temperature=0.01,
                max_tokens=max(2200, candidate_count * 650),
                retries=1,
                enable_thinking=False,
            )
        except Exception as error:
            print("[Committee] Fast pass failed; escalating once to deep JSON recovery.")
            print(f"[Committee] {type(error).__name__}: {error}")
            return self.client.reason_json(
                system_prompt=COMMITTEE_DEEP_PROMPT,
                payload=payload,
                task_name="investment_committee_recovery_v4_4_1",
                temperature=0.02,
                max_tokens=max(3500, candidate_count * 900),
                retries=1,
                enable_thinking=True,
            )

    def _candidate_payload(
        self,
        candidate,
        registry,
        guard,
    ) -> dict:

        analyst = (
            candidate.analyst
        )

        critic = (
            candidate.critic
        )

        analyst_meta = None

        if analyst is not None:

            analyst_meta = {
                "decision":
                    analyst.decision,

                "conviction":
                    analyst.conviction,

                "evidence_quality":
                    analyst.evidence_quality,
            }

        critic_meta = None

        if critic is not None:

            critic_meta = {
                "thesis_survives":
                    critic.thesis_survives,

                "adjusted_conviction":
                    critic.adjusted_conviction,
            }

        return {
            "symbol":
                candidate.symbol,

            "scanner_score":
                candidate.scanner_score,

            "flow_score":
                candidate.flow_score,

            "final_candidate_score":
                candidate.final_candidate_score,

            "deterministic_committee_guard":
                guard.to_dict(),

            "analyst":
                analyst_meta,

            "critic":
                critic_meta,

            "compact_evidence":
                self._compact_prompt_evidence(
                    registry
                ),
        }

    def _compact_prompt_evidence(
        self,
        registry,
    ) -> list[dict]:

        rows = []

        for evidence_id, item in sorted(
            registry.items()
        ):
            root = evidence_id.split(".", 1)[0]

            if root not in self.COMPACT_ROOTS:
                continue

            value = item.value

            # Avoid sending verbose nested/list evidence to the final LLM.
            # The deterministic engines have already summarized those inputs.
            if isinstance(value, (dict, list, tuple, set)):
                if evidence_id.endswith(".hard_overrides"):
                    pass
                else:
                    continue

            if not (
                evidence_id.endswith(self.COMPACT_SUFFIXES)
                or evidence_id in {
                    "unified_risk.risk_level",
                    "unified_risk.risk_score",
                    "unified_risk.hard_overrides",
                    "financial_health.score",
                    "financial_health.confidence_adjusted_score",
                    "accounting_quality.score",
                    "valuation.score",
                    "event_intelligence.score",
                    "macro_regime.score",
                    "macro_regime.regime",
                    "advanced_market.score",
                    "advanced_market.market_structure",
                }
            ):
                continue

            rows.append(
                {
                    "id": evidence_id,
                    "value": value,
                    "source": item.source,
                    "reliability": item.reliability,
                }
            )

        return rows

    def _normalize_rankings(
        self,
        rankings: list[dict],
    ) -> list[dict]:

        if not rankings:
            return []

        # Final order is deterministic after governance. Nemotron's proposed
        # rank is advisory only and cannot outrank the governed final score.
        rankings.sort(
            key=lambda item: (
                -self._number(item.get("committee_score", 0)),
                -self._number(item.get("confidence", 0)),
                str(item.get("symbol", "")),
            )
        )

        for index, item in enumerate(
            rankings,
            start=1,
        ):

            item[
                "rank"
            ] = index

        return rankings

    def _build_market_summary(
        self,
        rankings: list[dict],
    ) -> str:

        if not rankings:

            return (
                "No validated committee "
                "rankings were produced."
            )

        integrity_scores = [
            self._number(
                item.get(
                    "integrity_score",
                    0,
                )
            )

            for item
            in rankings
        ]

        average_integrity = (
            sum(
                integrity_scores
            )
            / len(
                integrity_scores
            )
        )

        return (
            f"{len(rankings)} finalist(s) "
            "were compared using Baby's "
            "registered evidence. "
            f"Average claim integrity: "
            f"{average_integrity:.1f}%. "
            "Unsupported claims were excluded "
            "from displayed rationales."
        )

    def _build_committee_summary(
        self,
        rankings: list[dict],
    ) -> str:

        if not rankings:

            return (
                "No validated finalists."
            )

        parts = []

        for item in rankings[:5]:

            parts.append(
                f"#{item['rank']} "
                f"{item['symbol']} "
                f"{item['decision']} "
                f"(committee "
                f"{self._number(item.get('committee_score')):.1f}, "
                f"confidence "
                f"{self._number(item.get('confidence')):.0f}%, "
                f"integrity "
                f"{self._number(item.get('integrity_score')):.0f}%)."
            )

        return " ".join(
            parts
        )

    def _number(
        self,
        value: Any,
    ) -> float:

        try:

            return float(
                value
            )

        except Exception:

            return 0.0