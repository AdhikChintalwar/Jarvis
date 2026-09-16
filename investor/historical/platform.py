from investor.point_in_time import PointInTimeResearchEngine
from .sec_pit_facts import SECPointInTimeFacts
from .financial_replay import HistoricalFinancialResolver

class HistoricalResearchPlatform:
    """SEC filing-time evidence -> immutable V5 snapshot."""
    def __init__(self,sec,store=None):
        self.sec=sec
        self.facts=SECPointInTimeFacts(sec)
        self.fin=HistoricalFinancialResolver()
        self.snapshots=PointInTimeResearchEngine(store=store)

    def build_sec_snapshot(self,symbol,cik,as_of,universe_as_of=None):
        facts=self.facts.facts_as_of(cik,as_of)
        evidence=list(self.fin.resolve(facts).values())
        return self.snapshots.build_snapshot(
            symbol,as_of,universe_as_of or str(as_of)[:10],None,evidence,
            provenance={"source":"SEC_EDGAR","cik":str(cik),"schema_version":"5.5"})
