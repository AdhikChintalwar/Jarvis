from __future__ import annotations

from dataclasses import asdict, is_dataclass
from enum import Enum
from typing import Any


class EvidenceBuilder:

    def build(
        self,
        scan_candidate,
        report: dict,
    ) -> dict:

        full = {
            "identity": {
                "ticker": report.get(
                    "ticker",
                    getattr(
                        scan_candidate,
                        "symbol",
                        "",
                    ),
                ),
                "company_name": report.get(
                    "company_name"
                ),
                "generated_at": report.get(
                    "generated_at"
                ),
            },

            "scanner": {
                "scanner_score": getattr(
                    scan_candidate,
                    "opportunity_score",
                    0,
                ),
                "flow_score": getattr(
                    scan_candidate,
                    "flow_score",
                    0,
                ),
                "flow_type": getattr(
                    scan_candidate,
                    "flow_type",
                    None,
                ),
                "relative_volume": getattr(
                    scan_candidate,
                    "relative_volume",
                    None,
                ),
                "volume_zscore": getattr(
                    scan_candidate,
                    "volume_zscore",
                    None,
                ),
                "daily_change_pct": getattr(
                    scan_candidate,
                    "daily_change_pct",
                    None,
                ),
                "gap_pct": getattr(
                    scan_candidate,
                    "gap_pct",
                    None,
                ),
                "close_location_pct": getattr(
                    scan_candidate,
                    "close_location_pct",
                    None,
                ),
                "breakout_20d": getattr(
                    scan_candidate,
                    "breakout_20d",
                    False,
                ),
                "breakdown_20d": getattr(
                    scan_candidate,
                    "breakdown_20d",
                    False,
                ),
                "flags": list(
                    getattr(
                        scan_candidate,
                        "flags",
                        [],
                    )
                    or []
                ),
            },

            "market": self._serialize(
                report.get("market")
            ),

            "technical": self._serialize(
                report.get("technical")
            ),

            "fundamentals": self._serialize(
                report.get("fundamentals")
            ),

            "financial_health": self._serialize(
                report.get("financial_health")
            ),

            "primary_financial": self._serialize(
                report.get("primary_financial")
            ),

            "classification": self._serialize(
                report.get("classification")
            ),

            "risk": self._serialize(
                report.get("risk")
            ),

            "sec": self._serialize(
                report.get("sec")
            ),

            "deep_sec": self._serialize(
                report.get("deep_sec")
            ),

            "catalysts": self._serialize(
                report.get("catalysts")
            ),

            "market_context": self._serialize(
                report.get("market_context")
            ),

            "data_quality": self._serialize(
                report.get("data_quality")
            ),

            "deterministic_thesis": self._serialize(
                report.get("thesis")
            ),

            "trade_plan": self._serialize(
                report.get("trade_plan")
            ),

            "abnormal_volume": self._serialize(
                report.get("abnormal_volume")
            ),
        }

        # Compress first, then clean. This is intentional:
        # primary-financial compression must see explicit null values so an
        # unresolved verified metric can retain {"value": None, ...} instead
        # of losing the value field before committee evidence is built.
        return self._clean(
            self.compress(full)
        )

    def compress(
        self,
        evidence: dict,
    ) -> dict:

        compact = {}

        for key in [
            "identity",
            "scanner",
        ]:
            if evidence.get(key):
                compact[key] = evidence[key]

        technical = evidence.get(
            "technical",
            {}
        )

        compact["technical"] = self._select(
            technical,
            [
                "price",
                "trend_signal",
                "momentum_signal",
                "rsi_14",
                "rsi14",
                "relative_volume",
                "ema_9",
                "ema_20",
                "ema_50",
                "ema_200",
                "sma_20",
                "sma_50",
                "sma_200",
                "atr",
                "atr_pct",
                "macd",
                "macd_signal",
                "distance_from_ema20_pct",
                "distance_from_ema50_pct",
                "week_52_high",
                "week_52_low",
            ],
        )

        market = evidence.get(
            "market",
            {}
        )

        compact["market"] = self._select(
            market,
            [
                "price",
                "daily_change_pct",
                "volume",
                "average_volume",
                "dollar_volume",
            ],
        )

        fundamentals = evidence.get(
            "fundamentals",
            {}
        )

        compact["fundamentals"] = self._select(
            fundamentals,
            [
                "market_cap",
                "trailing_pe",
                "forward_pe",
                "price_to_sales",
                "price_to_book",
                "revenue",
                "revenue_growth",
                "net_income",
                "profit_margin",
                "operating_margin",
                "cash",
                "debt",
                "free_cash_flow",
                "operating_cash_flow",
                "return_on_equity",
                "return_on_assets",
                "beta",
                "shares_outstanding",
                "float_shares",
                "short_ratio",
                "short_percent_float",
            ],
        )


        primary_financial = evidence.get(
            "primary_financial",
            {}
        )

        if primary_financial:
            verified = primary_financial.get(
                "verified_financials",
                {}
            )
            compact_verified = {}
            for metric in [
                "revenue", "revenue_growth_yoy", "revenue_cagr_3y",
                "gross_margin", "operating_margin", "net_margin",
                "operating_income", "net_income",
                "operating_cash_flow", "capex", "free_cash_flow",
                "cash", "short_term_investments", "debt",
                "cash_to_debt", "shares_change_yoy",
            ]:
                item = verified.get(metric)
                if not isinstance(item, dict):
                    continue
                compact_verified[metric] = {
                    "value": item.get("value"),
                    "source": item.get("source"),
                    "status": item.get("status"),
                    "confidence": item.get("confidence"),
                    "period": item.get("period"),
                }

            compact["primary_financial"] = {
                "schema_version": primary_financial.get("schema_version"),
                "primary_source": primary_financial.get("primary_source"),
                "secondary_source": primary_financial.get("secondary_source"),
                "verified_financials": compact_verified,
                "balance_sheet_snapshot": self._select(
                    primary_financial.get("balance_sheet_snapshot", {}),
                    ["anchor_date", "confidence", "status",
                     "freshness_days", "core_coverage", "optional_coverage"],
                ),
            }

        financial = evidence.get(
            "financial_health",
            {}
        )

        compact["financial_health"] = self._select(
            financial,
            [
                "score",
                "revenue_growth_score",
                "profitability_score",
                "cash_flow_score",
                "balance_sheet_score",
                "cash_to_debt_ratio",
                "cash_runway_years",
                "warnings",
                "strengths",
            ],
        )

        classification = evidence.get(
            "classification",
            {}
        )

        compact["classification"] = classification

        risk = evidence.get(
            "risk",
            {}
        )

        compact["risk"] = self._select(
            risk,
            [
                "overall_risk",
                "overall",
                "risk_level",
                "annualized_volatility",
                "maximum_drawdown",
                "average_daily_move",
                "largest_gain",
                "largest_drop",
                "gap_risk",
                "liquidity_risk",
                "trend_risk",
                "overextension",
                "warnings",
            ],
        )

        sec = evidence.get(
            "sec",
            {}
        )

        compact["sec"] = self._select(
            sec,
            [
                "cik",
                "dilution_risk",
                "summary",
                "warnings",
            ],
        )

        deep_sec = evidence.get(
            "deep_sec",
            {}
        )

        if deep_sec:

            compact["deep_sec"] = self._select(
                deep_sec,
                [
                    "filings_scanned",
                    "dilution_score",
                    "dilution_risk",
                    "distress_score",
                    "distress_risk",
                    "summary",
                ],
            )

            findings = (
                deep_sec.get(
                    "all_findings",
                    []
                )
                or []
            )

            compact[
                "deep_sec"
            ][
                "important_findings"
            ] = []

            for finding in findings[:8]:

                if not isinstance(
                    finding,
                    dict,
                ):
                    continue

                compact[
                    "deep_sec"
                ][
                    "important_findings"
                ].append(
                    {
                        "date": finding.get(
                            "filing_date"
                        ),
                        "form": finding.get(
                            "filing_form"
                        ),
                        "category": finding.get(
                            "category"
                        ),
                        "severity": finding.get(
                            "severity"
                        ),
                        "phrase": finding.get(
                            "phrase"
                        ),
                        "score": finding.get(
                            "score"
                        ),
                        "context": self._truncate(
                            finding.get(
                                "context"
                            ),
                            350,
                        ),
                    }
                )

        catalysts = evidence.get(
            "catalysts",
            {}
        )

        if catalysts:

            compact["catalysts"] = self._select(
                catalysts,
                [
                    "catalyst_score",
                    "positive_count",
                    "negative_count",
                    "high_importance_count",
                ],
            )

            catalyst_items = (
                catalysts.get(
                    "catalysts",
                    []
                )
                or []
            )

            compact[
                "catalysts"
            ][
                "recent"
            ] = []

            for catalyst in catalyst_items[:8]:

                if not isinstance(
                    catalyst,
                    dict,
                ):
                    continue

                compact[
                    "catalysts"
                ][
                    "recent"
                ].append(
                    {
                        "title": self._truncate(
                            catalyst.get(
                                "title"
                            ),
                            180,
                        ),
                        "source": catalyst.get(
                            "source"
                        ),
                        "published_at": catalyst.get(
                            "published_at"
                        ),
                        "category": catalyst.get(
                            "category"
                        ),
                        "importance": catalyst.get(
                            "importance"
                        ),
                    }
                )

        for key in [
            "market_context",
            "data_quality",
            "deterministic_thesis",
            "trade_plan",
        ]:

            if evidence.get(key):
                compact[key] = evidence[key]

        abnormal = evidence.get(
            "abnormal_volume",
            {}
        )

        if abnormal:

            compact[
                "abnormal_volume"
            ] = self._select(
                abnormal,
                [
                    "current_rvol",
                    "average_rvol_5d",
                    "abnormal_days",
                    "extreme_volume_days",
                    "bullish_events",
                    "bearish_events",
                    "accumulation_score",
                    "signal",
                ],
            )

        return self._clean(
            compact
        )

    def _select(
        self,
        source,
        keys,
    ):

        if not isinstance(
            source,
            dict,
        ):
            return {}

        result = {}

        for key in keys:

            if key in source:

                result[key] = source[
                    key
                ]

        return self._clean(
            result
        )

    def _truncate(
        self,
        value,
        limit,
    ):

        if value is None:
            return None

        text = str(value)

        if len(text) <= limit:
            return text

        return (
            text[:limit]
            + "..."
        )

    def _serialize(
        self,
        value: Any,
    ):

        if value is None:
            return None

        if isinstance(
            value,
            Enum,
        ):
            return value.value

        if is_dataclass(
            value
        ):

            return {
                key: self._serialize(
                    item
                )
                for key, item
                in asdict(
                    value
                ).items()
            }

        if isinstance(
            value,
            dict,
        ):

            return {
                str(key): self._serialize(
                    item
                )
                for key, item
                in value.items()
            }

        if isinstance(
            value,
            (
                list,
                tuple,
                set,
            ),
        ):

            return [
                self._serialize(
                    item
                )
                for item
                in value
            ]

        if isinstance(
            value,
            (
                str,
                int,
                float,
                bool,
            ),
        ):

            return value

        if hasattr(
            value,
            "__dict__",
        ):

            return {
                key: self._serialize(
                    item
                )
                for key, item
                in vars(
                    value
                ).items()
                if not key.startswith(
                    "_"
                )
            }

        return str(value)

    def _clean(
        self,
        value,
    ):

        if isinstance(
            value,
            dict,
        ):

            result = {}

            # Verified financial records intentionally use value=None to mean
            # "known metric, but unresolved/missing after evidence validation".
            # That is materially different from an absent key. Preserve the
            # explicit null whenever this dict is a status-bearing metric record.
            preserve_explicit_value_null = (
                "status" in value
                and "value" in value
                and value.get("value") is None
            )

            for key, item in value.items():

                if (
                    key == "value"
                    and item is None
                    and preserve_explicit_value_null
                ):
                    result[key] = None
                    continue

                cleaned = self._clean(
                    item
                )

                if cleaned is None:
                    continue

                if cleaned == {}:
                    continue

                if cleaned == []:
                    continue

                result[key] = cleaned

            return result

        if isinstance(
            value,
            list,
        ):

            result = []

            for item in value:

                cleaned = self._clean(
                    item
                )

                if cleaned is not None:
                    result.append(
                        cleaned
                    )

            return result

        return value