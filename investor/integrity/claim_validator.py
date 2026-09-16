from __future__ import annotations

from typing import Any

from investor.integrity.claim_models import (
    ClaimCategory,
    ClaimRecord,
    ClaimType,
    IntegrityResult,
)

from investor.integrity.numeric_validator import (
    NumericValidator,
)

from investor.integrity.semantic_validator import (
    SemanticValidator,
)


class ClaimValidator:

    def __init__(
        self,
    ):

        self.numeric_validator = (
            NumericValidator()
        )

        self.semantic_validator = (
            SemanticValidator()
        )

    def validate(
        self,
        raw_claims: list[dict],
        evidence_registry: dict,
    ) -> IntegrityResult:

        supported = []

        unsupported = []

        unknown = []

        evidence_used = set()

        warnings = []

        for index, raw in enumerate(
            raw_claims or []
        ):

            claim = self._parse_claim(
                raw,
                index,
            )

            if not claim.statement:

                claim.supported = False

                claim.validation_reason = (
                    "Empty claim statement."
                )

                unsupported.append(
                    claim
                )

                continue

            if (
                claim.claim_type
                == ClaimType.UNKNOWN
            ):

                claim.supported = True

                claim.validation_reason = (
                    "Explicitly classified UNKNOWN."
                )

                unknown.append(
                    claim
                )

                continue

            if not claim.evidence_ids:

                claim.supported = False

                claim.validation_reason = (
                    "No evidence IDs supplied."
                )

                unsupported.append(
                    claim
                )

                continue

            missing = [
                evidence_id

                for evidence_id
                in claim.evidence_ids

                if evidence_id
                not in evidence_registry
            ]

            if missing:

                claim.supported = False

                claim.validation_reason = (
                    "Unknown evidence ID(s): "
                    + ", ".join(
                        missing
                    )
                )

                unsupported.append(
                    claim
                )

                continue

            semantic_result = (
                self.semantic_validator.validate(
                    statement=
                        claim.statement,

                    evidence_ids=
                        claim.evidence_ids,
                )
            )

            if not semantic_result.valid:

                claim.supported = False

                claim.validation_reason = (
                    "Semantic validation failed: "
                    + semantic_result.reason
                )

                unsupported.append(
                    claim
                )

                continue

            numeric_result = (
                self.numeric_validator.validate(
                    statement=
                        claim.statement,

                    evidence_ids=
                        claim.evidence_ids,

                    evidence_registry=
                        evidence_registry,
                )
            )

            if not numeric_result.valid:

                claim.supported = False

                claim.validation_reason = (
                    "Numeric validation failed: "
                    + numeric_result.reason
                )

                unsupported.append(
                    claim
                )

                continue

            claim.supported = True

            claim.validation_reason = (
                "Evidence IDs exist and claim passed "
                "numeric and semantic validation."
            )

            supported.append(
                claim
            )

            evidence_used.update(
                claim.evidence_ids
            )

        total_non_unknown = (
            len(supported)
            + len(unsupported)
        )

        if total_non_unknown:

            integrity_score = (
                len(supported)
                / total_non_unknown
                * 100.0
            )

        else:

            integrity_score = 100.0

        if unsupported:

            warnings.append(
                f"{len(unsupported)} unsupported "
                "committee claim(s) were rejected."
            )

        if integrity_score < 80:

            warnings.append(
                "Committee claim integrity is below 80%."
            )

        if integrity_score < 60:

            warnings.append(
                "Committee output requires review before "
                "using the investment decision."
            )

        return IntegrityResult(
            passed=(
                len(unsupported)
                == 0
            ),

            supported_claims=
                supported,

            unsupported_claims=
                unsupported,

            unknown_claims=
                unknown,

            evidence_used=sorted(
                evidence_used
            ),

            integrity_score=round(
                integrity_score,
                1,
            ),

            warnings=
                warnings,
        )

    def _parse_claim(
        self,
        raw: dict[str, Any],
        index: int,
    ) -> ClaimRecord:

        if not isinstance(raw, dict):
            raw = {
                "claim_id": f"MALFORMED_{index}",
                "statement": str(raw),
                "type": "INFERENCE",
                "category": "OTHER",
                "evidence_ids": [],
                "confidence": 0,
            }

        claim_type_raw = str(
            raw.get(
                "type",
                "INFERENCE",
            )
        ).upper().strip()

        category_raw = str(
            raw.get(
                "category",
                "OTHER",
            )
        ).upper().strip()

        try:

            claim_type = ClaimType(
                claim_type_raw
            )

        except Exception:

            claim_type = (
                ClaimType.INFERENCE
            )

        try:

            category = ClaimCategory(
                category_raw
            )

        except Exception:

            category = (
                ClaimCategory.OTHER
            )

        try:

            confidence = float(
                raw.get(
                    "confidence",
                    0,
                )
            )

        except Exception:

            confidence = 0.0

        evidence_ids = (
            raw.get(
                "evidence_ids",
                [],
            )
            or []
        )

        if isinstance(
            evidence_ids,
            str,
        ):

            evidence_ids = [
                evidence_ids
            ]

        return ClaimRecord(
            claim_id=str(
                raw.get(
                    "claim_id",
                    f"claim_{index + 1}",
                )
            ),

            statement=str(
                raw.get(
                    "statement",
                    "",
                )
            ).strip(),

            claim_type=
                claim_type,

            category=
                category,

            evidence_ids=[
                str(item)
                for item
                in evidence_ids
            ],

            confidence=max(
                0.0,
                min(
                    100.0,
                    confidence,
                ),
            ),
        )