from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class SemanticValidationResult:
    valid: bool
    reason: str


class SemanticValidator:
    """
    Deterministic financial semantic guardrails.

    This is deliberately conservative.

    It does not attempt general semantic reasoning.
    It blocks specific high-risk inference patterns that
    previously caused unsupported committee statements.
    """

    RULES = [
        {
            "patterns": [
                r"\binstitutional buying\b",
                r"\binstitutional accumulation\b",
                r"\binstitutional selling\b",
                r"\binstitutional volume\b",
                r"\bsmart money\b",
                r"\binstitutions are buying\b",
                r"\binstitutions are accumulating\b",
            ],

            "required_tokens": [
                "institutional",
                "13f",
                "ownership",
            ],

            "reason": (
                "Institutional activity requires direct "
                "institutional ownership or filing evidence."
            ),
        },

        {
            "patterns": [
                r"\binsider selling\b",
                r"\binsider buying\b",
                r"\binsiders are selling\b",
                r"\binsiders are buying\b",
            ],

            "required_tokens": [
                "insider",
                "form4",
                "form_4",
                "ownership_transaction",
            ],

            "reason": (
                "Insider activity requires direct insider "
                "transaction evidence."
            ),
        },

        {
            "patterns": [
                r"\bdiluted shareholders\b",
                r"\bshares were diluted\b",
                r"\bdilution occurred\b",
                r"\bissued new shares\b",
                r"\bcompleted offering\b",
            ],

            "required_tokens": [
                "issuance",
                "shares_issued",
                "completed_offering",
                "424b",
                "offering_completed",
            ],

            "reason": (
                "Registration evidence alone does not prove "
                "that issuance or dilution occurred."
            ),
        },

        {
            "patterns": [
                r"\bcompetitive threat\b",
                r"\blosing market share\b",
                r"\btaking market share\b",
                r"\bcompetition from\b",
            ],

            "required_tokens": [
                "competition",
                "competitor",
                "market_share",
            ],

            "reason": (
                "Competitor and market-share claims require "
                "explicit competitive evidence."
            ),
        },

        {
            "patterns": [
                r"\bnet retention\b",
                r"\bnet revenue retention\b",
                r"\bnrr\b",
                r"\bcustomer retention\b",
            ],

            "required_tokens": [
                "retention",
                "nrr",
                "customer_metric",
            ],

            "reason": (
                "Retention claims require explicit "
                "customer-metric evidence."
            ),
        },

        {
            "patterns": [
                r"\bdriven by .*headline",
                r"\bcaused by .*news",
                r"\bdue to .*headline",
                r"\brally because of\b",
                r"\bsurge because of\b",
            ],

            "required_tokens": [
                "catalyst",
                "news",
            ],

            "reason": (
                "A causal explanation for a price move "
                "requires explicit catalyst or news evidence."
            ),
        },
    ]

    FORBIDDEN_VOLUME_LEAPS = [
        r"\bvolume confirms institutional\b",
        r"\bvolume confirmation from institutions\b",
        r"\binstitutional volume confirmation\b",
        r"\brelative volume proves\b",
        r"\bvolume proves accumulation\b",
    ]

    def validate(
        self,
        statement: str,
        evidence_ids: list[str],
    ) -> SemanticValidationResult:

        normalized_statement = (
            statement
            or ""
        ).lower()

        normalized_ids = [
            str(item).lower()
            for item
            in evidence_ids
        ]

        for pattern in (
            self.FORBIDDEN_VOLUME_LEAPS
        ):

            if re.search(
                pattern,
                normalized_statement,
            ):

                return SemanticValidationResult(
                    valid=False,

                    reason=(
                        "Trading volume cannot establish "
                        "institutional activity."
                    ),
                )

        for rule in self.RULES:

            matched = any(
                re.search(
                    pattern,
                    normalized_statement,
                )

                for pattern
                in rule[
                    "patterns"
                ]
            )

            if not matched:
                continue

            has_required_evidence = any(
                token
                in evidence_id

                for evidence_id
                in normalized_ids

                for token
                in rule[
                    "required_tokens"
                ]
            )

            if not has_required_evidence:

                return SemanticValidationResult(
                    valid=False,

                    reason=rule[
                        "reason"
                    ],
                )

        return SemanticValidationResult(
            valid=True,

            reason=(
                "No unsupported high-risk semantic "
                "claim pattern detected."
            ),
        )