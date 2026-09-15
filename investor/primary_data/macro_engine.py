from __future__ import annotations
from dataclasses import dataclass, asdict
from .macro_provider import MacroObservation


@dataclass
class MacroContext:
    regime: str
    score: float
    metrics: dict
    observations: list[str]

    def to_dict(self):
        return asdict(self)


class MacroEngine:
    def analyze(self, series: dict[str, list[MacroObservation]]) -> MacroContext:
        metrics = {}
        notes = []
        score = 50.0

        def latest(name):
            rows = series.get(name, [])
            return rows[-1].value if rows else None

        def yoy(name, periods):
            rows = series.get(name, [])
            if len(rows) <= periods or rows[-periods-1].value == 0:
                return None
            return rows[-1].value / rows[-periods-1].value - 1.0

        fed = latest("fed_funds")
        y2 = latest("treasury_2y")
        y10 = latest("treasury_10y")
        unemployment = latest("unemployment")

        metrics["fed_funds"] = fed
        metrics["treasury_2y"] = y2
        metrics["treasury_10y"] = y10
        metrics["yield_curve_10y_2y"] = (y10 - y2) if y10 is not None and y2 is not None else None
        metrics["unemployment"] = unemployment
        metrics["cpi_yoy"] = yoy("cpi", 12)
        metrics["core_cpi_yoy"] = yoy("core_cpi", 12)
        metrics["pce_yoy"] = yoy("pce", 12)
        metrics["core_pce_yoy"] = yoy("core_pce", 12)
        metrics["payrolls_yoy"] = yoy("payrolls", 12)
        metrics["real_gdp_yoy"] = yoy("real_gdp", 4)

        curve = metrics["yield_curve_10y_2y"]
        if curve is not None:
            if curve < 0:
                score -= 8
                notes.append("2Y Treasury yield is above 10Y Treasury yield.")
            else:
                score += 3

        core_pce = metrics["core_pce_yoy"]
        if core_pce is not None:
            if core_pce > 0.03:
                score -= 7
                notes.append("Core PCE inflation is above 3% year over year.")
            elif core_pce < 0.025:
                score += 5

        if unemployment is not None and unemployment >= 5.0:
            score -= 6
            notes.append("Unemployment rate is at or above 5%.")

        score = max(0.0, min(100.0, score))
        regime = "neutral"
        if score >= 62:
            regime = "supportive"
        elif score <= 38:
            regime = "restrictive"

        return MacroContext(regime, score, metrics, notes)
