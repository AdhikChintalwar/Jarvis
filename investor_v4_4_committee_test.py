import sys, types
if "yfinance" not in sys.modules:
    yf = types.ModuleType("yfinance")
    yf.download = lambda *args, **kwargs: None
    class _Ticker:
        def __init__(self, *args, **kwargs):
            self.info = {}
            self.news = []
    yf.Ticker = _Ticker
    sys.modules["yfinance"] = yf

if "openai" not in sys.modules:
    openai = types.ModuleType("openai")
    class _OpenAI:
        def __init__(self, *args, **kwargs): pass
    openai.OpenAI = _OpenAI
    sys.modules["openai"] = openai

from investor.committee.committee import NemotronInvestmentCommittee
from investor.committee.models import (
    CandidateIntelligence, AnalystVerdict, CriticVerdict
)


class FakeClient:
    def reason_json(self, **kwargs):
        # Deliberately tries to over-promote CRWD and returns rankings out of order.
        return {
            "rankings": [
                {
                    "symbol": "CRWD",
                    "rank": 1,
                    "committee_score": 99,
                    "decision": "TOP_CANDIDATE",
                    "confidence": 99,
                    "claims": [
                        {
                            "claim_id": "CRWD_1",
                            "statement": "Unified risk is very high.",
                            "type": "FACT",
                            "category": "RISK",
                            "evidence_ids": ["unified_risk.risk_level"],
                            "confidence": 99,
                        },
                        {
                            "claim_id": "CRWD_2",
                            "statement": "Further research is warranted before any action.",
                            "type": "INFERENCE",
                            "category": "ACTION",
                            "evidence_ids": ["unified_risk.risk_level"],
                            "confidence": 90,
                        },
                    ],
                },
                {
                    "symbol": "AAPL",
                    "rank": 2,
                    "committee_score": 75,
                    "decision": "CANDIDATE",
                    "confidence": 90,
                    "claims": [
                        {
                            "claim_id": "AAPL_1",
                            "statement": "Financial evidence is fully covered.",
                            "type": "FACT",
                            "category": "STRENGTH",
                            "evidence_ids": ["financial_health.evidence_coverage"],
                            "confidence": 95,
                        },
                        {
                            "claim_id": "AAPL_2",
                            "statement": "Research case has moderate deterministic risk.",
                            "type": "INFERENCE",
                            "category": "RATIONALE",
                            "evidence_ids": ["unified_risk.risk_level"],
                            "confidence": 85,
                        },
                    ],
                },
            ]
        }


def evidence(fin, acct, val, event, macro, market, risk, hard=None):
    return {
        "financial_health": {
            "score": fin, "confidence_adjusted_score": fin,
            "evidence_confidence": 88, "evidence_coverage": 100,
        },
        "accounting_quality": {"score": acct, "confidence": 80, "coverage": 100},
        "valuation": {"score": val, "confidence": 78, "coverage": 100},
        "event_intelligence": {"score": event, "confidence": 75, "coverage": 100},
        "macro_regime": {"score": macro, "confidence": 86, "coverage": 100},
        "advanced_market": {"score": market, "confidence": 68, "coverage": 100},
        "unified_risk": {
            "risk_score": risk,
            "risk_level": "VERY_HIGH" if risk >= 70 else "MODERATE",
            "confidence": 75,
            "coverage": 100,
            "hard_overrides": list(hard or []),
        },
    }


aapl = CandidateIntelligence(
    symbol="AAPL",
    scanner_score=70,
    flow_score=60,
    evidence=evidence(73, 57, 18, 50, 40, 52, 42),
    analyst=AnalystVerdict(symbol="AAPL", decision="CANDIDATE", conviction=75, evidence_quality=90),
    critic=CriticVerdict(symbol="AAPL", thesis_survives=True, adjusted_conviction=70),
    final_candidate_score=70,
    passed_gate=True,
)

crwd = CandidateIntelligence(
    symbol="CRWD",
    scanner_score=85,
    flow_score=90,
    evidence=evidence(
        62, 68, 14, 50, 40, 50, 80,
        hard=["Extreme realized-volatility hard override triggered."],
    ),
    analyst=AnalystVerdict(symbol="CRWD", decision="CANDIDATE", conviction=80, evidence_quality=90),
    critic=CriticVerdict(symbol="CRWD", thesis_survives=True, adjusted_conviction=75),
    final_candidate_score=80,
    passed_gate=True,
)

committee = NemotronInvestmentCommittee(FakeClient())
result = committee.rank([crwd, aapl])
by_symbol = {r["symbol"]: r for r in result["rankings"]}

assert by_symbol["CRWD"]["decision"] == "WATCH", by_symbol["CRWD"]
assert by_symbol["CRWD"]["maximum_decision"] == "WATCH"
assert by_symbol["CRWD"]["governance_status"] == "RISK_CONSTRAINED"
assert by_symbol["CRWD"]["committee_score"] < 99
assert by_symbol["CRWD"]["confidence"] < 99
assert by_symbol["AAPL"]["decision"] == "CANDIDATE"
assert result["rankings"][0]["committee_score"] >= result["rankings"][1]["committee_score"]
assert [r["rank"] for r in result["rankings"]] == list(range(1, len(result["rankings"]) + 1))

print("V4.4 final-committee governance contract: PASS")
for r in result["rankings"]:
    print(
        r["symbol"],
        "rank=", r["rank"],
        "final=", r["committee_score"],
        "deterministic=", r["deterministic_score"],
        "llm=", r["llm_score"],
        "decision=", r["decision"],
        "max=", r["maximum_decision"],
        "confidence=", r["confidence"],
        "authority=", r["evidence_authority"],
        "governance=", r["governance_status"],
    )
