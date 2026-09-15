from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .sec_company_facts import SECCompanyFactsClient
from .financial_normalizer import FinancialNormalizer, NormalizedFact
from .metric_semantics import MetricSemantics


@dataclass
class MetricSeries:
    metric: str
    taxonomy: str | None
    concept: str | None
    unit: str | None
    annual: list[NormalizedFact]
    quarterly: list[NormalizedFact]
    instantaneous: list[NormalizedFact]
    semantic_confidence: float = 0.0
    calculation_allowed: bool = False
    semantic_note: str = ""
    series_quality: float = 0.0
    latest_economic_date: str | None = None

    def to_dict(self) -> dict:
        return {
            "metric": self.metric,
            "taxonomy": self.taxonomy,
            "concept": self.concept,
            "unit": self.unit,
            "annual": [x.to_dict() for x in self.annual],
            "quarterly": [x.to_dict() for x in self.quarterly],
            "instantaneous": [x.to_dict() for x in self.instantaneous],
            "semantic_confidence": self.semantic_confidence,
            "calculation_allowed": self.calculation_allowed,
            "semantic_note": self.semantic_note,
            "series_quality": self.series_quality,
            "latest_economic_date": self.latest_economic_date,
        }


class FinancialStatements:
    CONCEPTS = {
        "revenue": [
            ("us-gaap", "RevenueFromContractWithCustomerExcludingAssessedTax"),
            ("us-gaap", "RevenueFromContractWithCustomerIncludingAssessedTax"),
            ("us-gaap", "SalesRevenueNet"),
            ("us-gaap", "SalesRevenueGoodsNet"),
            ("us-gaap", "SalesRevenueServicesNet"),
            ("us-gaap", "Revenues"),
        ],
        "cost_of_revenue": [
            ("us-gaap", "CostOfRevenue"),
            ("us-gaap", "CostOfGoodsAndServicesSold"),
            ("us-gaap", "CostOfGoodsSold"),
        ],
        "gross_profit": [("us-gaap", "GrossProfit")],
        "operating_income": [("us-gaap", "OperatingIncomeLoss")],
        "net_income": [
            ("us-gaap", "NetIncomeLoss"),
            ("us-gaap", "ProfitLoss"),
            ("us-gaap", "NetIncomeLossAvailableToCommonStockholdersBasic"),
        ],
        "operating_cash_flow": [
            ("us-gaap", "NetCashProvidedByUsedInOperatingActivities"),
            ("us-gaap", "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"),
        ],
        "capex": [
            ("us-gaap", "PaymentsToAcquirePropertyPlantAndEquipment"),
            ("us-gaap", "PaymentsForPropertyPlantAndEquipment"),
        ],
        "cash": [
            ("us-gaap", "CashAndCashEquivalentsAtCarryingValue"),
            ("us-gaap", "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"),
        ],
        "short_term_investments": [
            ("us-gaap", "ShortTermInvestments"),
            ("us-gaap", "MarketableSecuritiesCurrent"),
        ],
        "assets": [("us-gaap", "Assets")],
        "liabilities": [("us-gaap", "Liabilities")],
        "equity": [
            ("us-gaap", "StockholdersEquity"),
            ("us-gaap", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"),
        ],
        "debt_current": [
            ("us-gaap", "LongTermDebtCurrent"),
            ("us-gaap", "ShortTermBorrowings"),
            ("us-gaap", "DebtCurrent"),
        ],
        "debt_noncurrent": [
            ("us-gaap", "LongTermDebtNoncurrent"),
            ("us-gaap", "LongTermDebt"),
        ],
        "shares_outstanding": [
            ("us-gaap", "CommonStockSharesOutstanding"),
            ("dei", "EntityCommonStockSharesOutstanding"),
        ],
        "weighted_average_diluted_shares": [
            ("us-gaap", "WeightedAverageNumberOfDilutedSharesOutstanding"),
        ],
        "eps_diluted": [("us-gaap", "EarningsPerShareDiluted")],
    }

    INSTANT_METRICS = {
        "cash", "short_term_investments", "assets", "liabilities",
        "equity", "debt_current", "debt_noncurrent", "shares_outstanding",
    }

    UNIT_PREFS = {
        "shares_outstanding": ("shares",),
        "weighted_average_diluted_shares": ("shares",),
        "eps_diluted": ("USD/shares", "USD-per-shares"),
    }

    def __init__(self, client=None):
        self.client = client or SECCompanyFactsClient()
        self.normalizer = FinancialNormalizer()
        self.semantics = MetricSemantics()

    def build(self, ticker: str) -> dict[str, MetricSeries]:
        raw = self.client.company_facts(ticker=ticker)
        return {
            metric: self._resolve_metric(raw, metric, aliases)
            for metric, aliases in self.CONCEPTS.items()
        }

    def _resolve_metric(self, raw, metric, aliases):
        candidates = []

        for alias_index, (taxonomy, concept_name) in enumerate(aliases):
            concept = self.client.concept(raw, taxonomy, concept_name)
            if not concept:
                continue

            preferred = self.UNIT_PREFS.get(metric, ("USD",))
            unit, rows = self.client.best_unit(concept, preferred)
            if not rows:
                continue

            normalized = self.normalizer.normalize_units(
                metric, taxonomy, concept_name, unit or "", rows
            )
            if not normalized:
                continue

            if metric in self.INSTANT_METRICS:
                annual, quarterly = [], []
                instantaneous = self.normalizer.instantaneous(normalized)
                usable = instantaneous
            else:
                annual = self.normalizer.annual(normalized)
                quarterly = self.normalizer.quarterly(normalized)
                instantaneous = []
                usable = annual or quarterly

            semantic = self.semantics.evaluate(
                metric, taxonomy, concept_name
            )

            latest_date = (
                max(x.end for x in usable)
                if usable else None
            )

            quality = self._series_quality(
                metric=metric,
                usable=usable,
                semantic_confidence=semantic.confidence,
            )

            candidates.append(
                (
                    MetricSeries(
                        metric=metric,
                        taxonomy=taxonomy,
                        concept=concept_name,
                        unit=unit,
                        annual=annual,
                        quarterly=quarterly,
                        instantaneous=instantaneous,
                        semantic_confidence=semantic.confidence,
                        calculation_allowed=semantic.allowed_for_calculation,
                        semantic_note=semantic.note,
                        series_quality=quality,
                        latest_economic_date=latest_date,
                    ),
                    alias_index,
                )
            )

        if not candidates:
            return MetricSeries(
                metric, None, None, None, [], [], [],
                0.0, False, "No standardized concept selected.",
                0.0, None,
            )

        newest_date = max(
            (
                series.latest_economic_date
                for series, _ in candidates
                if series.latest_economic_date
            ),
            default=None,
        )

        def rank(item):
            series, alias_index = item

            recency = self._recency_score(
                series.latest_economic_date,
                newest_date,
            )

            # For shares, stale/zero series must lose even if their semantic
            # confidence is nominally higher.
            sanity = self._sanity_score(
                metric,
                series,
            )

            return (
                sanity,
                recency,
                series.semantic_confidence,
                series.series_quality,
                -alias_index,
            )

        best, _ = max(candidates, key=rank)
        return best

    @staticmethod
    def _recency_score(value, newest):
        if not value or not newest:
            return 0.0
        try:
            v = date.fromisoformat(value)
            n = date.fromisoformat(newest)
        except ValueError:
            return 0.0

        gap = abs((n - v).days)

        if gap <= 45:
            return 1.0
        if gap <= 180:
            return 0.8
        if gap <= 430:
            return 0.5
        if gap <= 800:
            return 0.2
        return 0.0

    @staticmethod
    def _sanity_score(metric, series):
        usable = (
            series.instantaneous
            if series.instantaneous
            else series.annual
        )

        if not usable:
            return 0.0

        latest = usable[-1]

        if metric == "shares_outstanding":
            if latest.value <= 0:
                return 0.0

            # Require at least two positive observations for a high-quality
            # trend series.
            positives = [x for x in usable if x.value > 0]
            return 1.0 if len(positives) >= 2 else 0.5

        return 1.0

    @staticmethod
    def _series_quality(metric, usable, semantic_confidence):
        if not usable:
            return 0.0

        history = min(1.0, len(usable) / 4.0)
        latest = usable[-1]
        sanity = 1.0

        if metric == "shares_outstanding" and latest.value <= 0:
            sanity = 0.0

        return (
            semantic_confidence * 0.55
            + history * 0.25
            + sanity * 0.20
        )
