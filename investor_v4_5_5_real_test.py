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
print("V4.5.5 LIVE SCHEMA-RECOVERING DEEP INVESTMENT REASONING")
print("=" * 100)

committee = NemotronInvestmentCommittee(
    NemotronClient(use_cache=True)
)
result = committee.rank(candidates, deep_review=True)

print("=" * 100)
print("V4.5.5 DEEP REASONING INSPECTION")
print("=" * 100)
print("Provider status:", result.get("provider_status", "UNKNOWN"))
print("Committee schema:", result.get("committee_schema", {}))

rankings = result.get("rankings", [])
deliberations = result.get("deep_deliberation", {})

assert rankings, "No committee rankings returned."

for r in rankings:
    symbol = str(r.get("symbol", "")).upper()
    d = deliberations.get(symbol, {})

    print("-" * 100)
    print("Symbol              :", symbol)
    print("Rank                :", r.get("rank"))
    print("Final committee     :", r.get("committee_score"))
    print("Deterministic       :", r.get("deterministic_score"))
    print("Nemotron proposed   :", r.get("llm_score"))
    print("Decision            :", r.get("decision"))
    print("Maximum decision    :", r.get("maximum_decision"))
    print("Confidence          :", r.get("confidence"))
    print("Evidence authority  :", r.get("evidence_authority"))
    print("Module coverage     :", r.get("module_coverage"))
    print("Governance          :", r.get("governance_status"))
    print("Constraints         :", r.get("governance_constraints", []))
    print("Integrity           :", r.get("integrity_score"))
    print("Unsupported final   :", len(r.get("unsupported_claims", []) or []))

    print()
    print("DEEP DELIBERATION")
    print("  Status            :", d.get("status", "UNAVAILABLE"))
    print("  Bull score        :", d.get("bull_score"))
    print("  Bear score        :", d.get("bear_score"))
    print("  Synthesis score   :", d.get("synthesis_score"))
    print("  Confidence        :", d.get("confidence"))
    print("  Integrity         :", d.get("integrity_score"))
    print("  Unsupported       :", len(d.get("unsupported_claims", []) or []))

    claims = d.get("claims", []) or []
    bull = [c for c in claims if str(c.get("category","")).upper() == "STRENGTH"]
    risk = [c for c in claims if str(c.get("category","")).upper() == "RISK"]
    rationale = [c for c in claims if str(c.get("category","")).upper() == "RATIONALE"]

    print("  Bull claims:")
    if bull:
        for c in bull:
            print("    +", c.get("statement"))
            print("      evidence:", c.get("evidence_ids", []))
    else:
        print("    + none validated")

    print("  Bear / risk claims:")
    if risk:
        for c in risk:
            print("    -", c.get("statement"))
            print("      evidence:", c.get("evidence_ids", []))
    else:
        print("    - none validated")

    print("  Contradictions / synthesis:")
    if rationale:
        for c in rationale:
            print("    *", c.get("statement"))
            print("      evidence:", c.get("evidence_ids", []))
    else:
        print("    * none validated")

    print("  Unknowns:")
    unknowns = d.get("unresolved_questions", []) or []
    if unknowns:
        for u in unknowns:
            print("    ?", u)
    else:
        print("    ? none")

    unsupported = d.get("unsupported_claims", []) or []
    if unsupported:
        print("  Rejected deliberation output:")
        for u in unsupported:
            if isinstance(u, dict):
                print("    x", u.get("statement") or u.get("raw") or u)
                if u.get("evidence_ids"):
                    print("      evidence:", u.get("evidence_ids"))
                if u.get("reason"):
                    print("      reason:", u.get("reason"))
            else:
                print("    x", u)

    print()
    print("FINAL VALIDATED COMMITTEE CLAIMS")
    print("  Strength          :", r.get("strength"))
    print("  Risk              :", r.get("risk"))
    print("  Rationale         :", r.get("rationale"))
    print("  Action            :", r.get("action"))
    print("  Unknowns          :", r.get("unknowns", []))

# Governance invariants.
lookup = {str(r.get("symbol","")).upper(): r for r in rankings}
if "CRWD" in lookup:
    crwd = lookup["CRWD"]
    if crwd.get("maximum_decision") == "WATCH":
        assert crwd.get("decision") not in ("CANDIDATE", "TOP_CANDIDATE"), crwd

print("=" * 100)
print("RESULT: PASS")
print("V4.5.3 exposes deep reasoning + validation + governance for inspection.")
