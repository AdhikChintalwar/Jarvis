from __future__ import annotations

from dataclasses import dataclass, asdict


@dataclass
class CapexSemanticAssessment:
    comparable: bool
    status: str
    confidence: float
    primary_definition: str
    secondary_definition: str
    reason: str

    def to_dict(self):
        return asdict(self)


class CapexSemanticReconciler:
    """
    Determines whether SEC and Yahoo CapEx values are semantically comparable.

    V3.4.1 intentionally avoids declaring a numeric disagreement to be an
    accounting contradiction when the provider definitions are not proven
    equivalent.
    """

    # SEC concepts that normally represent purchases of PP&E / productive
    # fixed assets. These are the strongest direct comparison candidates.
    DIRECT_PPE_CONCEPTS = {
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "PaymentsForProceedsFromOtherPropertyPlantAndEquipment",
        "PaymentsToAcquireProductiveAssets",
        "PaymentsToAcquirePropertyPlantAndEquipmentAndIntangibleAssets",
    }

    # Concepts whose scope can be broader/different than a provider's generic
    # "Capital Expenditure" row. These require caution.
    BROAD_OR_AMBIGUOUS_CONCEPTS = {
        "PaymentsToAcquireBusinessesNetOfCashAcquired",
        "PaymentsToAcquireInvestments",
        "PaymentsToAcquireIntangibleAssets",
        "PaymentsForSoftware",
        "PaymentsToAcquireOtherPropertyPlantAndEquipment",
    }

    def assess(
        self,
        primary_concept: str | None,
        secondary_label: str | None,
    ) -> CapexSemanticAssessment:
        if not primary_concept:
            return CapexSemanticAssessment(
                comparable=False,
                status="DEFINITION_UNVERIFIED",
                confidence=0.45,
                primary_definition="unknown",
                secondary_definition=secondary_label or "unknown",
                reason="SEC CapEx concept provenance is unavailable.",
            )

        if primary_concept in self.DIRECT_PPE_CONCEPTS:
            return CapexSemanticAssessment(
                comparable=True,
                status="COMPARABLE",
                confidence=0.90,
                primary_definition=primary_concept,
                secondary_definition=secondary_label or "Capital Expenditure",
                reason=(
                    "SEC concept represents direct productive/fixed-asset "
                    "capital expenditure and is reasonably comparable to the "
                    "Yahoo annual Capital Expenditure row."
                ),
            )

        if primary_concept in self.BROAD_OR_AMBIGUOUS_CONCEPTS:
            return CapexSemanticAssessment(
                comparable=False,
                status="DEFINITION_MISMATCH",
                confidence=0.80,
                primary_definition=primary_concept,
                secondary_definition=secondary_label or "Capital Expenditure",
                reason=(
                    "SEC concept scope is broader or materially different "
                    "from generic provider CapEx."
                ),
            )

        return CapexSemanticAssessment(
            comparable=False,
            status="DEFINITION_UNVERIFIED",
            confidence=0.55,
            primary_definition=primary_concept,
            secondary_definition=secondary_label or "Capital Expenditure",
            reason=(
                "No explicit semantic equivalence rule exists for this SEC "
                "CapEx concept."
            ),
        )
