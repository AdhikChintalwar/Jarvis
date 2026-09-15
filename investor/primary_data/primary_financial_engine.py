from __future__ import annotations

from datetime import datetime, timezone
from .validation_provenance import build_sec_validation_provenance
from .financial_statements import FinancialStatements
from .financial_trends import FinancialTrendEngine
from .balance_sheet_resolver import BalanceSheetResolver
from .annual_cross_validation import AnnualCrossValidationEngine
from .verified_financials import VerifiedFinancialBuilder
from .macro_provider import FREDProvider
from .macro_engine import MacroEngine


class PrimaryFinancialEngine:
    def __init__(self):
        self.statements = FinancialStatements()
        self.trends = FinancialTrendEngine()
        self.balance_sheet = BalanceSheetResolver()
        self.cross_validator = AnnualCrossValidationEngine()
        self.verified_builder = VerifiedFinancialBuilder()

    def analyze_company(self, ticker: str, validate_secondary: bool = True) -> dict:
        ticker = ticker.upper()
        statements = self.statements.build(ticker)
        trend_report = self.trends.analyze(statements)
        metrics = dict(trend_report.metrics)

        bs = self.balance_sheet.resolve(statements)
        bs_metrics = bs.metrics

        cash = self._bs_value(bs_metrics, "cash")
        short_inv = self._bs_value(bs_metrics, "short_term_investments")
        debt_current = self._bs_value(bs_metrics, "debt_current")
        debt_noncurrent = self._bs_value(bs_metrics, "debt_noncurrent")

        debt_parts = [x for x in (debt_current, debt_noncurrent) if x is not None]
        debt = sum(debt_parts) if debt_parts else None

        metrics["cash"] = cash
        metrics["short_term_investments"] = short_inv
        metrics["cash_plus_short_term_investments"] = (
            (cash or 0.0) + (short_inv or 0.0)
            if cash is not None or short_inv is not None else None
        )
        metrics["debt"] = debt
        metrics["cash_to_debt"] = (
            cash / debt
            if cash is not None and debt is not None and debt > 0 else None
        )
        liquid = metrics["cash_plus_short_term_investments"]
        metrics["liquid_assets_to_debt"] = (
            liquid / debt
            if liquid is not None and debt is not None and debt > 0 else None
        )

        periods = self._period_map(trend_report, bs)

        validation = None
        if validate_secondary:
            try:
                sec_provenance = build_sec_validation_provenance(
                    statements,
                    trend_report,
                )

                validation = self.cross_validator.validate(
                    ticker=ticker,
                    sec_metrics=metrics,
                    sec_periods=periods,
                    sec_provenance=sec_provenance,
                ).to_dict()
            except Exception as exc:
                validation = {
                    "status": "SECONDARY_VALIDATION_ERROR",
                    "error": str(exc),
                    "metrics": {},
                    "confidence": 0.0,
                }

        validation_metrics = validation.get("metrics", {}) if validation else {}

        verified = self.verified_builder.build(
            sec_metrics=metrics,
            validation=validation_metrics,
            periods=periods,
        )

        return {
            "schema_version": "3.5",
            "ticker": ticker,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "primary_source": "SEC EDGAR Company Facts / XBRL",
            "secondary_source": "Yahoo Finance annual statements",
            "trends": {
                "metrics": metrics,
                "warnings": trend_report.warnings,
                "diagnostics": trend_report.diagnostics,
            },
            "balance_sheet_snapshot": bs.to_dict(),
            "cross_validation": validation,
            "verified_financials": {
                k: v.to_dict() for k, v in verified.items()
            },
        }

    @staticmethod
    def _bs_value(metrics, key):
        item = metrics.get(key)
        return item.value if item else None

    @staticmethod
    def _period_map(trend_report, bs):
        revenue_period = (
            trend_report.diagnostics
            .get("revenue_period", {})
            .get("fact", {})
            .get("end")
        )

        periods = {}

        for metric in {
            "revenue", "revenue_growth_yoy", "revenue_cagr_3y",
            "gross_margin", "operating_margin", "net_margin",
            "operating_income", "net_income", "operating_cash_flow",
            "capex", "free_cash_flow",
        }:
            periods[metric] = revenue_period

        for metric in {
            "cash", "short_term_investments",
            "cash_plus_short_term_investments",
            "debt", "cash_to_debt", "liquid_assets_to_debt",
        }:
            periods[metric] = bs.anchor_date

        periods["shares_change_yoy"] = (
            trend_report.diagnostics
            .get("shares_change_yoy", {})
            .get("latest_date")
        )

        return periods

    def analyze_macro(self):
        provider = FREDProvider()
        raw = provider.snapshot()
        context = MacroEngine().analyze(raw)
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source": "Federal Reserve Bank of St. Louis FRED",
            "context": context.to_dict(),
            "series": {
                key: [x.to_dict() for x in value]
                for key, value in raw.items()
            },
        }
