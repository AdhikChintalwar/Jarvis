import sys, types
if "yfinance" not in sys.modules:
    yf = types.ModuleType("yfinance")
    class _Ticker:
        def __init__(self, *args, **kwargs): pass
    yf.Ticker = _Ticker
    sys.modules["yfinance"] = yf

from types import SimpleNamespace
from investor.unified_risk import UnifiedRiskEngine

engine = UnifiedRiskEngine()

base = {
    "financial_health": SimpleNamespace(
        quality_score=75, confidence=90, coverage=100
    ),
    "accounting_quality": SimpleNamespace(
        score=70, confidence=85, coverage=100
    ),
    "valuation": SimpleNamespace(
        score=55, confidence=80, coverage=100
    ),
    "event_intelligence": SimpleNamespace(
        score=50, confidence=80, coverage=100, risks=[]
    ),
    "macro_regime": SimpleNamespace(
        score=45, confidence=85, regime="NEUTRAL"
    ),
    "advanced_market": SimpleNamespace(
        score=55, confidence=70, market_structure="mixed",
        signals={
            "realized_volatility_20d": {
                "value": 28.0, "confidence": 0.70
            }
        }
    ),
    "market_data": {
        "average_dollar_volume_20d": 150_000_000
    },
}

normal = engine.analyze(base)
assert normal.coverage == 100.0, normal.coverage
assert not normal.hard_overrides
assert normal.dimensions["market_volatility"]["state"] == "low"
assert normal.dimensions["liquidity"]["state"] == "low"

extreme = dict(base)
extreme["advanced_market"] = SimpleNamespace(
    score=55, confidence=70, market_structure="mixed",
    signals={
        "realized_volatility_20d": {
            "value": 98.0, "confidence": 0.70
        }
    }
)
high = engine.analyze(extreme)
assert high.risk_score >= 80.0, high.risk_score
assert high.hard_overrides, high.hard_overrides
assert high.position_risk_multiplier <= 0.40

missing = dict(base)
missing.pop("market_data")
unknown = engine.analyze(missing)
assert unknown.dimensions["liquidity"]["score"] is None
assert "average_dollar_volume" in unknown.unknowns
# Missing liquidity must not itself trigger high risk.
assert not any("liquidity hard override" in x.lower() for x in unknown.hard_overrides)

print("V4.2 unified-risk contract: PASS")
print("normal:", normal.risk_score, normal.risk_level,
      "confidence:", normal.confidence, "coverage:", normal.coverage)
print("extreme-vol override:", high.risk_score, high.risk_level,
      "multiplier:", high.position_risk_multiplier)
print("missing-neutral coverage:", unknown.coverage,
      "unknowns:", unknown.unknowns)
