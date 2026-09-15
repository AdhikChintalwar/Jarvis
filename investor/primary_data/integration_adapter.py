from __future__ import annotations


class PrimaryFinancialIntegrationAdapter:
    """
    Compatibility adapter for Baby's existing FinancialEngine /
    StockAnalyzer.

    It intentionally returns a plain dict so the current analyzer can adopt
    V3.3 without requiring an immediate full model rewrite.
    """

    def to_financial_engine_payload(
        self,
        primary_report: dict,
    ) -> dict:
        verified = primary_report.get(
            "verified_financials",
            {}
        )

        def value(name):
            item = verified.get(name, {})
            return item.get("value")

        def confidence(name):
            item = verified.get(name, {})
            return item.get("confidence", 0.0)

        return {
            "revenue": value("revenue"),
            "revenue_growth": value("revenue_growth_yoy"),
            "gross_margin": value("gross_margin"),
            "operating_margin": value("operating_margin"),
            "profit_margin": value("net_margin"),
            "operating_cash_flow": value("operating_cash_flow"),
            "free_cash_flow": value("free_cash_flow"),
            "cash": value("cash"),
            "debt": value("debt"),
            "cash_to_debt": value("cash_to_debt"),
            "shares_change_yoy": value("shares_change_yoy"),
            "primary_financial_confidence": self._average_confidence(
                verified
            ),
            "primary_financial_schema": primary_report.get(
                "schema_version"
            ),
            "primary_financial_source": primary_report.get(
                "primary_source"
            ),
            "primary_financial_evidence": verified,
        }

    @staticmethod
    def _average_confidence(verified):
        values = [
            float(item.get("confidence", 0.0))
            for item in verified.values()
            if item.get("value") is not None
        ]

        return (
            sum(values) / len(values)
            if values else 0.0
        )
