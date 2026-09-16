from dataclasses import dataclass, field


@dataclass
class InvestmentThesis:
    decision: str

    bull_case: list[str] = field(
        default_factory=list
    )

    base_case: list[str] = field(
        default_factory=list
    )

    bear_case: list[str] = field(
        default_factory=list
    )

    reasons: list[str] = field(
        default_factory=list
    )


class ThesisEngine:

    def build(
        self,
        technical,
        risk,
        financial,
        classification,
        sec_analysis,
        catalysts,
        market_context,
        data_quality,
    ):

        bull = []
        base = []
        bear = []
        reasons = []

        if (
            technical.trend_signal.value
            in {
                "bullish",
                "strong_bullish",
            }
        ):
            bull.append(
                "Primary price trend is bullish."
            )

        if (
            technical.macd_histogram
            is not None
            and technical.macd_histogram > 0
        ):
            bull.append(
                "MACD momentum remains positive."
            )

        if (
            financial.score >= 70
        ):
            bull.append(
                "Financial health is strong."
            )

        if (
            catalysts.positive_count
            > catalysts.negative_count
        ):
            bull.append(
                "Recent catalyst balance is positive."
            )

        if (
            market_context.regime
            == "risk_on"
        ):
            bull.append(
                "Broad market regime is supportive."
            )

        if (
            technical.rsi_14
            is not None
            and technical.rsi_14 >= 75
        ):
            bear.append(
                "RSI indicates extreme short-term extension."
            )

        if (
            technical.relative_volume
            is not None
            and technical.relative_volume < 0.8
        ):
            bear.append(
                "Latest volume is below its recent average."
            )

        if (
            risk.annualized_volatility
            is not None
            and risk.annualized_volatility >= 100
        ):
            bear.append(
                "Historical volatility is extreme."
            )

        if (
            risk.max_drawdown
            is not None
            and risk.max_drawdown >= 50
        ):
            bear.append(
                "Historical drawdown profile is severe."
            )

        if (
            financial.score < 40
        ):
            bear.append(
                "Financial-health score is weak."
            )

        if (
            sec_analysis.dilution_risk
            in {
                "high",
                "very_high",
            }
        ):
            bear.append(
                "SEC filing pattern indicates elevated dilution risk."
            )

        if classification.is_speculative:
            bear.append(
                "Stock is classified as speculative."
            )

        if (
            market_context.regime
            == "risk_off"
        ):
            bear.append(
                "Broad market conditions are risk-off."
            )

        base.append(
            (
                f"Current trend classification: "
                f"{technical.trend_signal.value}."
            )
        )

        base.append(
            (
                f"Financial health: "
                f"{financial.score:.1f}/100."
            )
        )

        base.append(
            (
                f"Overall risk: "
                f"{risk.overall_risk.value}."
            )
        )

        decision = self._decision(
            bull=bull,
            bear=bear,
            technical=technical,
            financial=financial,
            classification=classification,
            data_quality=data_quality,
        )

        reasons.extend(
            bull[:3]
        )

        reasons.extend(
            bear[:5]
        )

        return InvestmentThesis(
            decision=decision,
            bull_case=bull,
            base_case=base,
            bear_case=bear,
            reasons=reasons,
        )

    def _decision(
        self,
        bull,
        bear,
        technical,
        financial,
        classification,
        data_quality,
    ):

        if data_quality.score < 55:
            return "INSUFFICIENT_DATA"

        severe_extension = (
            technical.rsi_14 is not None
            and technical.rsi_14 >= 80
        )

        extreme_volatility = (
            classification
            .is_high_volatility
        )

        if (
            severe_extension
            and extreme_volatility
        ):
            return "WAIT"

        if (
            classification.is_speculative
            and len(bear) >= 3
        ):
            return "AVOID_OR_WATCH"

        if (
            len(bull) >= 4
            and len(bear) <= 2
            and financial.score >= 55
        ):
            return "CONSIDER"

        if len(bear) >= 5:
            return "AVOID"

        return "WATCH"