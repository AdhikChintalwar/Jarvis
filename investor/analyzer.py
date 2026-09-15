from __future__ import annotations
from investor.position_sizing import PositionSizingEngine
from datetime import datetime
from investor.abnormal_volume import AbnormalVolumeEngine
from investor.sec_filing_analyzer import SECFilingAnalyzer
from investor.trade_plan import TradePlanEngine
from investor.catalyst_engine import (
    CatalystEngine,
)

from investor.data_quality import (
    DataQualityEngine,
)

from investor.financial_engine import (
    FinancialEngine,
)
from investor.accounting_quality import AccountingQualityEngine
from investor.valuation_engine import ValuationEngine
from investor.event_intelligence import EventIntelligenceEngine
from investor.macro_regime import MacroRegimeEngine

from investor.indicators import (
    TechnicalIndicatorEngine,
)

from investor.market_context import (
    MarketContextEngine,
)

from investor.models import (
    Evidence,
    EvidenceQuality,
    FundamentalMetrics,
    MarketMetrics,
    StockReport,
)

from investor.providers.yahoo_provider import (
    YahooFinanceProvider,
)

from investor.risk_engine import (
    RiskEngine,
)

from investor.scoring_engine import (
    StockScoringEngine,
)

from investor.sec_client import (
    SECClient,
)

from investor.stock_classifier import (
    StockClassifier,
)

from investor.thesis_engine import (
    ThesisEngine,
)

from investor.primary_data import (
    PrimaryFinancialEngine,
    PrimaryFinancialIntegrationAdapter,
)


class StockAnalyzer:

    def __init__(
        self,
        provider=None,
    ):

        self.provider = (
            provider
            or YahooFinanceProvider()
        )

        self.technical_engine = (
            TechnicalIndicatorEngine()
        )

        self.risk_engine = (
            RiskEngine()
        )
        self.abnormal_volume_engine = (
            AbnormalVolumeEngine()
        )

        self.deep_sec_engine = (
            SECFilingAnalyzer()
        )

        self.trade_plan_engine = (
            TradePlanEngine()
        )

        self.position_sizing_engine = (
            PositionSizingEngine()
        )

        self.scoring_engine = (
            StockScoringEngine()
        )

        self.stock_classifier = (
            StockClassifier()
        )

        self.financial_engine = (
            FinancialEngine()
        )

        self.accounting_quality_engine = AccountingQualityEngine()
        self.valuation_engine = ValuationEngine()
        self.event_intelligence_engine = EventIntelligenceEngine()
        self.macro_regime_engine = MacroRegimeEngine()

        self.sec_client = (
            SECClient()
        )

        self.catalyst_engine = (
            CatalystEngine()
        )

        self.market_context_engine = (
            MarketContextEngine()
        )

        self.data_quality_engine = (
            DataQualityEngine()
        )

        self.thesis_engine = (
            ThesisEngine()
        )

        self.primary_financial_engine = (
            PrimaryFinancialEngine()
        )

        self.primary_financial_adapter = (
            PrimaryFinancialIntegrationAdapter()
        )

    def analyze(
        self,
        ticker: str,
    ):

        ticker = (
            ticker
            .upper()
            .strip()
        )

        print(
            "[1/9] Loading market data..."
        )

        history = (
            self.provider.get_history(
                ticker,
                period="1y",
                interval="1d",
            )
        )

        info = (
            self.provider
            .get_company_info(
                ticker
            )
        )

        quote = (
            self.provider
            .get_quote(
                ticker
            )
        )

        print(
            "[2/9] Calculating technical indicators..."
        )

        technical = (
            self.technical_engine
            .analyze(
                history
            )
        )

        market = (
            self._build_market(
                history,
                info,
                quote,
            )
        )

        fundamentals = (
            self._build_fundamentals(
                info
            )
        )

        # Financial statements are no longer sourced from Yahoo ``info``.
        # SEC/XBRL is primary; dated Yahoo annual statements are validation
        # evidence only. Market/valuation fields remain on the prototype
        # provider until dedicated primary providers replace them.
        print(
            "[3/10] Loading verified financial statements..."
        )

        primary_financial = None
        primary_financial_warning = None

        try:
            primary_financial = (
                self.primary_financial_engine
                .analyze_company(ticker)
            )

            payload = (
                self.primary_financial_adapter
                .to_financial_engine_payload(
                    primary_financial
                )
            )

            self._apply_primary_financials(
                fundamentals,
                payload,
            )

        except Exception as error:
            primary_financial_warning = (
                f"Primary financial intelligence unavailable: {error}"
            )
            print(
                "Primary financial warning:",
                error,
            )

        print(
            "[4/10] Calculating risk..."
        )

        risk = (
            self.risk_engine
            .analyze(
                history=history,
                market=market,
                technical=technical,
            )
        )

        print(
            "[5/10] Classifying stock..."
        )

        classification = (
            self.stock_classifier
            .classify(
                market_cap=(
                    fundamentals
                    .market_cap
                ),

                float_shares=(
                    fundamentals
                    .float_shares
                ),

                annualized_volatility=(
                    risk
                    .annualized_volatility
                ),

                revenue_growth=(
                    fundamentals
                    .revenue_growth
                ),

                profitable=(
                    fundamentals
                    .profit_margin
                    is not None
                    and fundamentals
                    .profit_margin > 0
                ),
            )
        )

        print(
            "[6/10] Analyzing financial health..."
        )

        financial_health = (
            self.financial_engine
            .analyze(
                fundamentals,
                primary_financial=primary_financial,
            )
        )

        print("\n[7/14] Analyzing accounting quality...")
        accounting_quality = self.accounting_quality_engine.analyze(primary_financial)

        print("[8/14] Analyzing valuation...")
        valuation = self.valuation_engine.analyze(
            market=market,
            fundamentals=fundamentals,
            primary_financial=primary_financial,
        )

        print(
            "[9/14] Checking SEC filings..."
        )

        try:

            sec_analysis = (
                self.sec_client
                .analyze_ticker(
                    ticker
                )
            )

        except Exception as error:

            print(
                "SEC warning:",
                error,
            )

            from investor.sec_client import (
                SECAnalysis,
            )

            sec_analysis = (
                SECAnalysis(
                    cik=None
                )
            )

        try:
            deep_sec = self.deep_sec_engine.analyze(sec_analysis)
        except Exception as error:
            print("Deep SEC warning:", error)
            from investor.sec_filing_analyzer import DeepSECAnalysis
            deep_sec = DeepSECAnalysis()

        print(
            "[10/14] Checking catalysts and event intelligence..."
        )

        news = (
            self.provider
            .get_news(
                ticker
            )
        )

        catalyst_analysis = (
            self.catalyst_engine
            .analyze(
                news
            )
        )

        event_intelligence = self.event_intelligence_engine.analyze(
            sec_analysis=sec_analysis,
            news_items=news,
            deep_sec=deep_sec,
        )

        print(
            "[11/14] Analyzing market environment..."
        )

        market_context = (
            self.market_context_engine
            .analyze()
        )

        print(
            "[12/14] Analyzing macro and market regime..."
        )

        macro_regime = self.macro_regime_engine.analyze()

        print(
            "[13/14] Finalizing deterministic evidence..."
        )

        score = (
            self.scoring_engine
            .score(
                market=market,
                technical=technical,
                fundamentals=(
                    fundamentals
                ),
                risk=risk,
                primary_financial=primary_financial,
                accounting_quality=accounting_quality,
                valuation=valuation,
            )
        )

        print(
            "[14/14] Building investment thesis..."
        )

        data_quality = (
            self.data_quality_engine
            .analyze(
                market=market,
                technical=technical,
                fundamentals=(
                    fundamentals
                ),
                sec_analysis=(
                    sec_analysis
                ),
                catalysts=(
                    catalyst_analysis
                ),
            )
        )

        thesis = (
            self.thesis_engine
            .build(
                technical=technical,
                risk=risk,

                financial=(
                    financial_health
                ),

                classification=(
                    classification
                ),

                sec_analysis=(
                    sec_analysis
                ),

                catalysts=(
                    catalyst_analysis
                ),

                market_context=(
                    market_context
                ),

                data_quality=(
                    data_quality
                ),
            )
        )

        company_name = (
            info.get("longName")
            or info.get("shortName")
            or ticker
        )

        return {
            "ticker": ticker,

            "company_name":
                company_name,

            "generated_at":
                datetime.now()
                .isoformat(),

            "market":
                market,

            "technical":
                technical,

            "fundamentals":
                fundamentals,

            "primary_financial":
                primary_financial,

            "primary_financial_warning":
                primary_financial_warning,

            "risk":
                risk,

            "score":
                score,

            "classification":
                classification,

            "financial_health":
                financial_health,

            "accounting_quality":
                accounting_quality,

            "valuation":
                valuation,

            "sec":
                sec_analysis,

            "deep_sec":
                deep_sec,

            "event_intelligence":
                event_intelligence,

            "catalysts":
                catalyst_analysis,

            "market_context":
                market_context,

            "macro_regime":
                macro_regime,

            "data_quality":
                data_quality,

            "thesis":
                thesis,
        }

    def _apply_primary_financials(
        self,
        fundamentals,
        payload,
    ):
        """
        Replace statement-derived Yahoo fields with verified SEC-primary
        values. Missing/unresolved primary values stay missing rather than
        silently falling back to Yahoo TTM fundamentals.
        """

        mapping = {
            "revenue": "revenue",
            "revenue_growth": "revenue_growth",
            "net_income": "net_income",
            "profit_margin": "profit_margin",
            "operating_margin": "operating_margin",
            "total_cash": "cash",
            "total_debt": "debt",
            "free_cash_flow": "free_cash_flow",
            "operating_cash_flow": "operating_cash_flow",
        }

        evidence = payload.get(
            "primary_financial_evidence",
            {},
        )

        for field_name, payload_name in mapping.items():
            metric_name = {
                "revenue_growth": "revenue_growth_yoy",
                "profit_margin": "net_margin",
                "total_cash": "cash",
                "total_debt": "debt",
            }.get(payload_name, payload_name)

            item = evidence.get(metric_name, {})
            status = item.get("status")

            # MATERIAL_DISAGREEMENT is represented as value=None by the
            # verified builder. MISSING also remains None. Do not revive the
            # old Yahoo-info value in either case.
            value = payload.get(payload_name)
            setattr(fundamentals, field_name, value)

        return fundamentals

    def _build_market(
        self,
        history,
        info,
        quote,
    ):

        latest = (
            history.iloc[-1]
        )

        current = (
            quote.get(
                "last_price"
            )
            or float(
                latest["Close"]
            )
        )

        if len(history) >= 2:

            previous = float(
                history.iloc[-2][
                    "Close"
                ]
            )

        else:

            previous = quote.get(
                "previous_close"
            )

        change = None
        change_pct = None

        if (
            current is not None
            and previous
        ):

            change = (
                current - previous
            )

            change_pct = (
                change
                / previous
                * 100
            )

        volume = float(
            latest["Volume"]
        )

        avg_volume = float(
            history[
                "Volume"
            ]
            .tail(20)
            .mean()
        )

        dollar_volume = (
            current
            * avg_volume
            if current is not None
            else None
        )

        bid = info.get(
            "bid"
        )

        ask = info.get(
            "ask"
        )

        spread_pct = None

        if (
            bid
            and ask
            and bid > 0
        ):

            midpoint = (
                bid + ask
            ) / 2

            spread_pct = (
                (ask - bid)
                / midpoint
                * 100
            )

        return MarketMetrics(
            current_price=(
                float(current)
                if current is not None
                else None
            ),

            previous_close=previous,

            daily_change=change,

            daily_change_pct=(
                change_pct
            ),

            volume=volume,

            average_volume=(
                avg_volume
            ),

            dollar_volume=(
                dollar_volume
            ),

            day_high=float(
                latest["High"]
            ),

            day_low=float(
                latest["Low"]
            ),

            bid=bid,

            ask=ask,

            bid_ask_spread_pct=(
                spread_pct
            ),
        )

    def _build_fundamentals(
        self,
        info,
    ):

        return FundamentalMetrics(
            market_cap=(
                info.get(
                    "marketCap"
                )
            ),

            trailing_pe=(
                info.get(
                    "trailingPE"
                )
            ),

            forward_pe=(
                info.get(
                    "forwardPE"
                )
            ),

            price_to_sales=(
                info.get(
                    "priceToSalesTrailing12Months"
                )
            ),

            price_to_book=(
                info.get(
                    "priceToBook"
                )
            ),

            revenue=(
                info.get(
                    "totalRevenue"
                )
            ),

            revenue_growth=(
                info.get(
                    "revenueGrowth"
                )
            ),

            net_income=(
                info.get(
                    "netIncomeToCommon"
                )
            ),

            profit_margin=(
                info.get(
                    "profitMargins"
                )
            ),

            operating_margin=(
                info.get(
                    "operatingMargins"
                )
            ),

            total_cash=(
                info.get(
                    "totalCash"
                )
            ),

            total_debt=(
                info.get(
                    "totalDebt"
                )
            ),

            debt_to_equity=(
                info.get(
                    "debtToEquity"
                )
            ),

            free_cash_flow=(
                info.get(
                    "freeCashflow"
                )
            ),

            operating_cash_flow=(
                info.get(
                    "operatingCashflow"
                )
            ),

            return_on_equity=(
                info.get(
                    "returnOnEquity"
                )
            ),

            return_on_assets=(
                info.get(
                    "returnOnAssets"
                )
            ),

            beta=(
                info.get(
                    "beta"
                )
            ),

            shares_outstanding=(
                info.get(
                    "sharesOutstanding"
                )
            ),

            float_shares=(
                info.get(
                    "floatShares"
                )
            ),

            short_ratio=(
                info.get(
                    "shortRatio"
                )
            ),

            short_percent_float=(
                info.get(
                    "shortPercentOfFloat"
                )
            ),
        )