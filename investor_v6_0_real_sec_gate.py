import os, sys
from datetime import datetime, timedelta, timezone
from tempfile import TemporaryDirectory
from pathlib import Path

from investor.historical import SECHistoricalFilings, SECPointInTimeFacts, HistoricalFinancialResolver
from investor.point_in_time import PointInTimeSnapshotStore, PointInTimeResearchEngine
from investor.v6 import HistoricalProductionDecisionAdapter, HistoricalDecisionReplay

COMPANIES={
    "AAPL":{"cik":"320193"},
    "CRWD":{"cik":"1535527"},
}

def iso(d): return d.astimezone(timezone.utc).isoformat()

def boundary_test(sec,symbol,cik):
    filings=[f for f in sec.submissions(cik)
             if (f.get("form") or "").replace("/A","") in {"10-K","10-Q"}
             and not (f.get("form") or "").endswith("/A")]
    candidates=[]
    for f in reversed(filings):
        try:
            acc=sec.acceptance_datetime(cik,f["accessionNumber"],f)
        except Exception:
            continue
        if acc:
            candidates.append((f,datetime.fromisoformat(acc)))
            break
    if not candidates: raise RuntimeError(f"{symbol}: no filing with acceptance timestamp")
    filing,accepted=candidates[0]
    before=accepted-timedelta(seconds=1)
    after=accepted+timedelta(seconds=1)

    before_acc={x["accessionNumber"] for x in sec.filings_available(cik,iso(before))}
    after_acc={x["accessionNumber"] for x in sec.filings_available(cik,iso(after))}
    target=filing["accessionNumber"]
    assert target not in before_acc, f"{symbol}: filing leaked before acceptance"
    assert target in after_acc, f"{symbol}: filing absent after acceptance"

    pit=SECPointInTimeFacts(sec)
    before_facts=pit.facts_as_of(cik,iso(before))
    after_facts=pit.facts_as_of(cik,iso(after))
    def accessions(facts):
        return {x.accession for rows in facts.values() for x in rows}
    assert target not in accessions(before_facts), f"{symbol}: XBRL leaked before acceptance"
    # A filing can legally contain no eligible standard-taxonomy entity-wide fact,
    # so do not require target accession in Company Facts; report it instead.

    return filing,accepted,before_facts,after_facts,target in accessions(after_facts)

def snapshot_and_decision(symbol,cik,accepted,facts):
    resolved=HistoricalFinancialResolver().resolve(facts)
    with TemporaryDirectory() as td:
        store=PointInTimeSnapshotStore(Path(td)/"pit.db")
        engine=PointInTimeResearchEngine(store=store)
        asof=iso(accepted+timedelta(seconds=1))
        snap=engine.build_snapshot(symbol,asof,asof[:10],None,list(resolved.values()),
                                   provenance={"schema_version":"6.0-real-gate","cik":cik})
        replay=HistoricalDecisionReplay(HistoricalProductionDecisionAdapter())
        decision=replay.replay(snap)
    return snap,decision

def main():
    if not os.getenv("SEC_USER_AGENT"):
        raise RuntimeError("SEC_USER_AGENT missing from .env")
    sec=SECHistoricalFilings()
    print("BABY V6.0 REAL SEC RELEASE GATE")
    print("="*72)
    for symbol,cfg in COMPANIES.items():
        filing,accepted,before,after,has_target=boundary_test(sec,symbol,cfg["cik"])
        snap,decision=snapshot_and_decision(symbol,cfg["cik"],accepted,after)
        print(f"\n{symbol}")
        print(" form:",filing.get("form"))
        print(" accession:",filing.get("accessionNumber"))
        print(" accepted_utc:",iso(accepted))
        print(" before concepts:",len(before))
        print(" after concepts:",len(after))
        print(" target accession represented in Company Facts after acceptance:",has_target)
        print(" reconstructed metrics:",sorted(snap.evidence))
        print(" production replay scope:",decision.metadata.get("snapshot_schema"),
              "/ PARTIAL_PRODUCTION_FINANCIAL_HEALTH")
        print(" decision:",decision.state,"score:",decision.score,
              "confidence:",decision.confidence,"coverage:",decision.coverage)
        assert decision.coverage <= 20.0001, "partial replay must not masquerade as full module coverage"
    print("\nRESULT: PASS")
    print("No pre-acceptance filing/XBRL leakage detected for AAPL or CRWD.")
    print("Production DecisionEngine replay is intentionally PARTIAL until all historical V4.x modules are reconstructed.")

if __name__=="__main__":
    main()
