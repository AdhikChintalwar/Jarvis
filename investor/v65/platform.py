from __future__ import annotations
from tempfile import TemporaryDirectory
from pathlib import Path
from investor.historical import SECHistoricalFilings,SECPointInTimeFacts
from investor.point_in_time import PointInTimeSnapshotStore,PointInTimeResearchEngine
from .financials import CoherentHistoricalFinancialResolver
from .market import HistoricalMarketSnapshotEngine
from .macro import AlfredPointInTimeMacro
from .full_replay import FullHistoricalDecisionAdapter

class BabyHistoricalValidationPlatform:
    def __init__(self,sec=None):
        self.sec=sec or SECHistoricalFilings()
        self.facts=SECPointInTimeFacts(self.sec)
        self.fin=CoherentHistoricalFinancialResolver()
        self.market=HistoricalMarketSnapshotEngine()
        self.macro=AlfredPointInTimeMacro()
        self.replay=FullHistoricalDecisionAdapter()

    def research(self,symbol,cik,as_of,history=None,benchmark_history=None,sec_analysis=None):
        facts=self.facts.facts_as_of(cik,as_of)
        evidence=self.fin.resolve(facts)
        with TemporaryDirectory() as td:
            eng=PointInTimeResearchEngine(PointInTimeSnapshotStore(Path(td)/"pit.db"))
            snap=eng.build_snapshot(symbol,as_of,str(as_of)[:10],None,list(evidence.values()),
                                    provenance={"schema_version":"6.5","cik":str(cik)})
        market=self.market.build(symbol,history,as_of,benchmark_history) if history is not None else None
        macro=self.macro.analyze(as_of)
        result=self.replay.evaluate(snap,market=market,macro=macro,sec_analysis=sec_analysis)
        return {"snapshot":snap,"market":market,"macro":macro,"decision":result}
