from dataclasses import dataclass, field


@dataclass
class DataQualityReport:
    score: float
    grade: str

    available_fields: int
    expected_fields: int

    missing: list[str] = field(
        default_factory=list
    )

    warnings: list[str] = field(
        default_factory=list
    )


class DataQualityEngine:

    def analyze(
        self,
        market,
        technical,
        fundamentals,
        sec_analysis=None,
        catalysts=None,
    ):

        checks = {
            "price":
                market.current_price,

            "volume":
                market.volume,

            "average_volume":
                market.average_volume,

            "market_cap":
                fundamentals.market_cap,

            "revenue_growth":
                fundamentals.revenue_growth,

            "profit_margin":
                fundamentals.profit_margin,

            "cash":
                fundamentals.total_cash,

            "debt":
                fundamentals.total_debt,

            "free_cash_flow":
                fundamentals.free_cash_flow,

            "float":
                fundamentals.float_shares,

            "rsi":
                technical.rsi_14,

            "atr":
                technical.atr_14,

            "ema_20":
                technical.ema_20,

            "ema_50":
                technical.ema_50,

            "ema_200":
                technical.ema_200,
        }

        missing = [
            name
            for name, value
            in checks.items()
            if value is None
        ]

        available = (
            len(checks)
            - len(missing)
        )

        score = (
            available
            / len(checks)
            * 75
        )

        if (
            sec_analysis is not None
            and sec_analysis.cik
            is not None
        ):
            score += 15

        if (
            catalysts is not None
            and catalysts.catalysts
        ):
            score += 10

        score = min(
            100,
            score,
        )

        if score >= 90:
            grade = "excellent"

        elif score >= 75:
            grade = "good"

        elif score >= 60:
            grade = "fair"

        else:
            grade = "poor"

        warnings = []

        if fundamentals.market_cap is None:
            warnings.append(
                "Market capitalization unavailable."
            )

        if (
            sec_analysis is not None
            and sec_analysis.cik is None
        ):
            warnings.append(
                "No SEC CIK found for ticker."
            )

        return DataQualityReport(
            score=round(
                score,
                1,
            ),

            grade=grade,

            available_fields=available,

            expected_fields=len(
                checks
            ),

            missing=missing,
            warnings=warnings,
        )