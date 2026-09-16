from types import SimpleNamespace

from investor import StockAnalyzer
from investor.committee.evidence_builder import EvidenceBuilder
from investor.committee.models import CandidateIntelligence, AnalystVerdict, CriticVerdict
from investor.committee.committee import NemotronInvestmentCommittee
from investor.committee.nemotron_client import NemotronClient


TICKERS = ["AAPL", "SLDE", "CRWD"]

builder = EvidenceBuilder()
candidates = []

for symbol in TICKERS:
    print("=" * 100)
    print("RESEARCH:", symbol)
    report = StockAnalyzer().analyze(symbol)

    scan = SimpleNamespace(
        symbol=symbol,
        opportunity_score=50.0,
        flow_score=50.0,
        flow_type="TEST",
        relative_volume=None,
        volume_zscore=None,
        daily_change_pct=None,
        gap_pct=None,
        close_location_pct=None,
        breakout_20d=False,
        breakdown_20d=False,
        flags=[],
    )

    evidence = builder.build(scan, report)

    candidates.append(
        CandidateIntelligence(
            symbol=symbol,
            scanner_score=50.0,
            flow_score=50.0,
            evidence=evidence,
            analyst=AnalystVerdict(
                symbol=symbol,
                decision="CANDIDATE",
                conviction=70.0,
                evidence_quality=90.0,
            ),
            critic=CriticVerdict(
                symbol=symbol,
                thesis_survives=True,
                adjusted_conviction=70.0,
            ),
            final_candidate_score=70.0,
            passed_gate=True,
        )
    )

print("=" * 100)
print("V4.4 LIVE FINAL INVESTMENT COMMITTEE")
print("=" * 100)

committee = NemotronInvestmentCommittee(
    NemotronClient(use_cache=False)
)
result = committee.rank(candidates)

for r in result["rankings"]:
    print("-" * 100)
    print("Symbol              :", r["symbol"])
    print("Rank                :", r["rank"])
    print("Final committee     :", r["committee_score"])
    print("Deterministic       :", r["deterministic_score"])
    print("Nemotron proposed   :", r["llm_score"])
    print("Decision            :", r["decision"])
    print("Maximum decision    :", r["maximum_decision"])
    print("Confidence          :", r["confidence"])
    print("Evidence authority  :", r["evidence_authority"])
    print("Module coverage     :", r["module_coverage"])
    print("Governance          :", r["governance_status"])
    print("Constraints         :", r["governance_constraints"])
    print("Integrity           :", r["integrity_score"])
    print("Strength            :", r["strongest_strength"])
    print("Risk                :", r["biggest_risk"])
    print("Rationale           :", r["why_ranked_here"])
    print("Action              :", r["preferred_action"])
    print("Unknowns            :", r["unknowns"])
    print("Unsupported claims  :", len(r["unsupported_claims"]))

# CRWD's V4.2.1 extreme-volatility hard override must remain sovereign
# if the live evidence still contains that override.
crwd = next((x for x in result["rankings"] if x["symbol"] == "CRWD"), None)
if crwd and crwd["governance_constraints"]:
    assert crwd["decision"] not in {"TOP_CANDIDATE", "CANDIDATE"}

print("=" * 100)
print("RESULT: PASS")
