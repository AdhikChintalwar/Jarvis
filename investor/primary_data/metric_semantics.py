from __future__ import annotations

from dataclasses import dataclass, asdict


@dataclass(frozen=True)
class ConceptSemantic:
    metric: str
    taxonomy: str
    concept: str
    semantic_role: str
    confidence: float
    allowed_for_calculation: bool
    note: str

    def to_dict(self):
        return asdict(self)


class MetricSemantics:
    """
    Explicit semantic allow-list.

    We do not use pretax income as operating income and do not infer
    financial-statement meaning merely because a concept contains
    superficially similar words.
    """

    SAFE = {
        ("revenue", "us-gaap", "RevenueFromContractWithCustomerExcludingAssessedTax"):
            ("revenue", 0.99, True, "Standard revenue concept."),
        ("revenue", "us-gaap", "RevenueFromContractWithCustomerIncludingAssessedTax"):
            ("revenue", 0.97, True, "Standard revenue concept including assessed tax."),
        ("revenue", "us-gaap", "SalesRevenueNet"):
            ("revenue", 0.95, True, "Legacy standardized net sales concept."),
        ("revenue", "us-gaap", "Revenues"):
            ("revenue", 0.92, True, "Standardized broad revenue concept."),

        ("gross_profit", "us-gaap", "GrossProfit"):
            ("gross_profit", 0.99, True, "Direct gross profit concept."),

        ("cost_of_revenue", "us-gaap", "CostOfRevenue"):
            ("cost_of_revenue", 0.97, True, "Direct cost of revenue concept."),
        ("cost_of_revenue", "us-gaap", "CostOfGoodsAndServicesSold"):
            ("cost_of_revenue", 0.95, True, "Cost of goods/services sold."),
        ("cost_of_revenue", "us-gaap", "CostOfGoodsSold"):
            ("cost_of_revenue", 0.93, True, "Cost of goods sold."),

        ("operating_income", "us-gaap", "OperatingIncomeLoss"):
            ("operating_income", 0.99, True, "Direct operating income/loss concept."),

        ("net_income", "us-gaap", "NetIncomeLoss"):
            ("net_income", 0.99, True, "Direct net income/loss concept."),
        ("net_income", "us-gaap", "ProfitLoss"):
            ("net_income", 0.95, True, "Standard profit/loss concept."),
        ("net_income", "us-gaap", "NetIncomeLossAvailableToCommonStockholdersBasic"):
            ("net_income_common", 0.90, True, "Net income available to common holders."),

        ("operating_cash_flow", "us-gaap", "NetCashProvidedByUsedInOperatingActivities"):
            ("operating_cash_flow", 0.99, True, "Direct operating cash-flow concept."),
        ("operating_cash_flow", "us-gaap", "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"):
            ("operating_cash_flow", 0.95, True, "Operating cash flow from continuing operations."),

        ("capex", "us-gaap", "PaymentsToAcquirePropertyPlantAndEquipment"):
            ("capex", 0.98, True, "Cash paid to acquire PP&E."),
        ("capex", "us-gaap", "PaymentsForPropertyPlantAndEquipment"):
            ("capex", 0.95, True, "Cash paid for PP&E."),

        ("shares_outstanding", "dei", "EntityCommonStockSharesOutstanding"):
            ("shares_outstanding", 0.90, True, "DEI entity common shares; requires continuity checks."),
        ("shares_outstanding", "us-gaap", "CommonStockSharesOutstanding"):
            ("shares_outstanding", 0.97, True, "Common shares outstanding."),
    }

    FORBIDDEN = {
        ("operating_income", "us-gaap",
         "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest"):
            "Pretax continuing-operations income is not operating income.",
    }

    def evaluate(
        self,
        metric: str,
        taxonomy: str | None,
        concept: str | None,
    ) -> ConceptSemantic:
        if not taxonomy or not concept:
            return ConceptSemantic(
                metric, taxonomy or "", concept or "",
                "missing", 0.0, False,
                "No standardized concept selected.",
            )

        forbidden = self.FORBIDDEN.get(
            (metric, taxonomy, concept)
        )
        if forbidden:
            return ConceptSemantic(
                metric, taxonomy, concept,
                "forbidden_substitution", 0.0, False,
                forbidden,
            )

        safe = self.SAFE.get(
            (metric, taxonomy, concept)
        )
        if safe:
            role, confidence, allowed, note = safe
            return ConceptSemantic(
                metric, taxonomy, concept,
                role, confidence, allowed, note,
            )

        # Other statement concepts remain usable for storage/provenance,
        # but are not automatically authorized for derived calculations.
        return ConceptSemantic(
            metric, taxonomy, concept,
            "unreviewed_standard_concept",
            0.70, False,
            "Concept not yet explicitly approved for derived calculations.",
        )
