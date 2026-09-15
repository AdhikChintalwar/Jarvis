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
        quality_score=67.62,
        evidence_confidence=87.57,
        evidence_coverage=100.0,
    ),
    "accounting_quality": SimpleNamespace(
        score=57.01, confidence=87.62, coverage=100
    ),
    "valuation": SimpleNamespace(
        score=18.48, confidence=77.5, coverage=100
    ),
    "event_intelligence": SimpleNamespace(
        score=50, confidence=64.05, coverage=75, risks=[]
    ),
    "macro_regime": SimpleNamespace(
        score=39.64, confidence=85.56, regime="NEUTRAL"
    ),
    "advanced_market": SimpleNamespace(
        score=52.45, confidence=67.86, market_structure="mixed",
        signals={
            "realized_volatility_20d": {
                "value": 23.31, "confidence": 0.70
            }
        }
    ),
    "liquidity_evidence": {
        "average_dollar_volume_20d": 2_000_000_000,
        "sessions": 20,
        "as_of": "2026-09-15",
        "source": "Derived from loaded Yahoo price/volume history",
        "authority": 0.70,
    },
    "market_data": {},
}

aapl_like = engine.analyze(base)

financial = aapl_like.dimensions["financial"]
liquidity = aapl_like.dimensions["liquidity"]

assert financial["confidence"] == 87.57, financial
assert financial["coverage"] == 100.0, financial
assert liquidity["score"] == 20.0, liquidity
assert liquidity["state"] == "low", liquidity
assert "average_dollar_volume_20d" not in aapl_like.unknowns
assert aapl_like.coverage == 100.0, aapl_like.coverage

crwd = dict(base)
crwd["financial_health"] = SimpleNamespace(
    quality_score=61.88,
    evidence_confidence=84.0,
    evidence_coverage=100.0,
)
crwd["advanced_market"] = SimpleNamespace(
    score=50.10, confidence=67.86, market_structure="mixed",
    signals={
        "realized_volatility_20d": {
            "value": 97.92, "confidence": 0.70
        }
    }
)
crwd_report = engine.analyze(crwd)
assert crwd_report.risk_score >= 80.0
assert crwd_report.hard_overrides
assert crwd_report.position_risk_multiplier <= 0.40

missing = dict(base)
missing.pop("liquidity_evidence")
missing_report = engine.analyze(missing)
assert missing_report.dimensions["liquidity"]["score"] is None
assert "average_dollar_volume_20d" in missing_report.unknowns
assert not missing_report.dimensions["liquidity"]["hard_override"]

print("V4.2.1 stabilization contract: PASS")
print("financial authority:", financial["confidence"], financial["coverage"])
print("liquidity:", liquidity["score"], liquidity["state"])
print("full coverage:", aapl_like.coverage)
print("CRWD-style override:", crwd_report.risk_score, crwd_report.risk_level,
      "multiplier:", crwd_report.position_risk_multiplier)
print("missing liquidity neutral:", missing_report.coverage, missing_report.unknowns)
