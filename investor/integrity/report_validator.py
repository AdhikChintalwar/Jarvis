from __future__ import annotations

from investor.integrity.claim_models import (
    ClaimCategory,
    IntegrityResult,
)


class ReportValidator:
    """
    Baby Evidence Integrity V2.2.1

    Converts validated claims into safe user-facing
    committee fields.

    IMPORTANT:

    Only supported claims may appear in:

        strongest_strength
        biggest_risk
        why_ranked_here
        preferred_action

    Unsupported claims remain available only in the
    audit section.

    UNKNOWN claims are displayed separately.
    """

    def build_safe_fields(
        self,
        integrity: IntegrityResult,
    ) -> dict:

        supported = (
            integrity.supported_claims
            or []
        )

        unknown_claims = (
            integrity.unknown_claims
            or []
        )

        strengths = self._statements(
            supported,
            ClaimCategory.STRENGTH,
        )

        risks = self._statements(
            supported,
            ClaimCategory.RISK,
        )

        rationales = self._statements(
            supported,
            ClaimCategory.RATIONALE,
        )

        actions = self._statements(
            supported,
            ClaimCategory.ACTION,
        )

        catalysts = self._statements(
            supported,
            ClaimCategory.CATALYST,
        )

        other = self._statements(
            supported,
            ClaimCategory.OTHER,
        )

        unknowns = [
            claim.statement
            for claim in unknown_claims
            if claim.statement
        ]

        strongest_strength = (
            strengths[0]
            if strengths
            else (
                "No validated strength claim."
            )
        )

        biggest_risk = (
            risks[0]
            if risks
            else (
                "No validated risk claim."
            )
        )

        preferred_action = (
            actions[0]
            if actions
            else (
                "No validated action claim."
            )
        )

        # ----------------------------------------------------
        # WHY
        #
        # Do NOT mix action instructions into rationale.
        #
        # Prefer:
        #   rationale
        #   strength
        #   risk
        #   catalyst
        #
        # This prevents:
        #
        # Why:
        #   "Enter long at..."
        #
        # when that belongs in Action.
        # ----------------------------------------------------

        why_parts = []

        why_parts.extend(
            rationales[:2]
        )

        if strengths:
            why_parts.extend(
                strengths[:1]
            )

        if risks:
            why_parts.extend(
                risks[:1]
            )

        if catalysts:
            why_parts.extend(
                catalysts[:1]
            )

        if not why_parts:

            why_parts.extend(
                other[:2]
            )

        why_ranked_here = (
            " ".join(
                self._dedupe(
                    why_parts
                )
            )
            if why_parts
            else (
                "No validated committee "
                "rationale was available."
            )
        )

        return {
            "strongest_strength":
                strongest_strength,

            "biggest_risk":
                biggest_risk,

            "why_ranked_here":
                why_ranked_here,

            "preferred_action":
                preferred_action,

            "unknowns":
                self._dedupe(
                    unknowns
                ),

            # Additional structured fields.
            #
            # Existing committee.py does not have to
            # consume these immediately, but they are
            # useful for future UI/report rendering.
            "verified_strengths":
                self._dedupe(
                    strengths
                ),

            "verified_risks":
                self._dedupe(
                    risks
                ),

            "verified_rationales":
                self._dedupe(
                    rationales
                ),

            "verified_actions":
                self._dedupe(
                    actions
                ),

            "verified_catalysts":
                self._dedupe(
                    catalysts
                ),
        }

    def _statements(
        self,
        claims,
        category,
    ) -> list[str]:

        results = []

        for claim in claims:

            if (
                claim.category
                != category
            ):
                continue

            statement = (
                claim.statement
                or ""
            ).strip()

            if statement:
                results.append(
                    statement
                )

        return self._dedupe(
            results
        )

    def _dedupe(
        self,
        items: list[str],
    ) -> list[str]:

        seen = set()

        result = []

        for item in items:

            normalized = (
                item
                .strip()
                .lower()
            )

            if not normalized:
                continue

            if normalized in seen:
                continue

            seen.add(
                normalized
            )

            result.append(
                item.strip()
            )

        return result