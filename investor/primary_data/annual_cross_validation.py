from __future__ import annotations

from dataclasses import dataclass, asdict

from .yahoo_annual_adapter import YahooAnnualFinancialAdapter
from .financial_reconciler import PeriodAwareFinancialReconciler
from .capex_semantics import CapexSemanticReconciler


@dataclass
class CrossValidationSummary:
    metrics: dict
    confidence: float
    strong_agreements: int
    agreements: int
    reviews: int
    disagreements: int
    definition_mismatches: int
    primary_only: int
    secondary_only: int

    def to_dict(self):
        return asdict(self)


class AnnualCrossValidationEngine:
    def __init__(self):
        self.yahoo = YahooAnnualFinancialAdapter()
        self.reconciler = PeriodAwareFinancialReconciler()
        self.capex_semantics = CapexSemanticReconciler()

    def validate(self, ticker, sec_metrics, sec_periods, sec_provenance=None):
        secondary = self.yahoo.fetch(ticker)
        results = {}
        sec_provenance = sec_provenance or {}

        mappings = {
            "revenue": "revenue",
            "operating_income": "operating_income",
            "net_income": "net_income",
            "operating_cash_flow": "operating_cash_flow",
            "cash": "cash",
            "debt": "total_debt",
        }

        for metric, yahoo_metric in mappings.items():
            fact = self._best_fact(secondary.get(yahoo_metric, []), sec_periods.get(metric))
            results[metric] = self.reconciler.reconcile(
                metric,
                sec_metrics.get(metric),
                sec_periods.get(metric),
                fact.value if fact else None,
                fact.period_end if fact else None,
            ).to_dict()

        # CapEx gets explicit semantic comparison.
        capex_fact = self._best_fact(
            secondary.get("capex", []),
            sec_periods.get("capex"),
        )
        capex_prov = sec_provenance.get("capex", {})
        semantic = self.capex_semantics.assess(
            capex_prov.get("concept"),
            capex_fact.label if capex_fact else None,
        )

        capex_result = self.reconciler.reconcile(
            "capex",
            sec_metrics.get("capex"),
            sec_periods.get("capex"),
            capex_fact.value if capex_fact else None,
            capex_fact.period_end if capex_fact else None,
            semantic_assessment=semantic,
        )
        results["capex"] = capex_result.to_dict()

        # Margins are independently derived from same-period Yahoo facts.
        for margin, numerator in (
            ("gross_margin", "gross_profit"),
            ("operating_margin", "operating_income"),
            ("net_margin", "net_income"),
        ):
            target = sec_periods.get(margin)
            rev = self._best_fact(secondary.get("revenue", []), target)
            num = self._best_fact(secondary.get(numerator, []), target)

            value = None
            period = None
            if rev and num and rev.value not in (None, 0) and rev.period_end == num.period_end:
                value = num.value / rev.value
                period = rev.period_end

            results[margin] = self.reconciler.reconcile(
                margin,
                sec_metrics.get(margin),
                target,
                value,
                period,
            ).to_dict()

        # FCF comparison inherits CapEx semantic comparability.
        target = sec_periods.get("free_cash_flow")
        ocf = self._best_fact(secondary.get("operating_cash_flow", []), target)
        y_capex = self._best_fact(secondary.get("capex", []), target)

        yahoo_fcf = None
        yahoo_period = None
        if ocf and y_capex and ocf.period_end == y_capex.period_end:
            yahoo_fcf = ocf.value - abs(y_capex.value)
            yahoo_period = ocf.period_end

        if semantic.comparable:
            results["free_cash_flow"] = self.reconciler.reconcile(
                "free_cash_flow",
                sec_metrics.get("free_cash_flow"),
                target,
                yahoo_fcf,
                yahoo_period,
            ).to_dict()
        else:
            fcf_semantic = self.capex_semantics.assess(
                capex_prov.get("concept"),
                y_capex.label if y_capex else None,
            )
            # Preserve SEC FCF rather than turning it into an artificial
            # disagreement caused by a non-equivalent CapEx definition.
            results["free_cash_flow"] = self.reconciler.reconcile(
                "free_cash_flow",
                sec_metrics.get("free_cash_flow"),
                target,
                yahoo_fcf,
                yahoo_period,
                semantic_assessment=fcf_semantic,
            ).to_dict()

        return self._summary(results)

    @staticmethod
    def _best_fact(facts, target):
        if not facts:
            return None
        if target:
            exact = [x for x in facts if x.period_end == target]
            if exact:
                return exact[0]
            from datetime import date
            try:
                d = date.fromisoformat(target)
                return min(
                    facts,
                    key=lambda x: abs((date.fromisoformat(x.period_end) - d).days),
                )
            except Exception:
                pass
        return facts[0]

    @staticmethod
    def _summary(results):
        statuses = [x["status"] for x in results.values()]
        excluded = {"MISSING", "SECONDARY_ONLY"}
        conf = [x["confidence"] for x in results.values() if x["status"] not in excluded]
        return CrossValidationSummary(
            metrics=results,
            confidence=sum(conf) / len(conf) if conf else 0.0,
            strong_agreements=statuses.count("STRONG_AGREEMENT"),
            agreements=statuses.count("AGREEMENT") + statuses.count("MINOR_DIFFERENCE"),
            reviews=(
                statuses.count("REVIEW")
                + statuses.count("PERIOD_MISMATCH")
                + statuses.count("DEFINITION_UNVERIFIED")
                + statuses.count("VALUE_AGREEMENT_PERIOD_UNVERIFIED")
                + statuses.count("VALUE_DISAGREEMENT_PERIOD_UNVERIFIED")
            ),
            disagreements=statuses.count("MATERIAL_DISAGREEMENT"),
            definition_mismatches=statuses.count("DEFINITION_MISMATCH"),
            primary_only=statuses.count("PRIMARY_ONLY"),
            secondary_only=statuses.count("SECONDARY_ONLY"),
        )
