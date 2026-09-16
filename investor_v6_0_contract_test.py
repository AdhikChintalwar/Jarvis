from tempfile import TemporaryDirectory
from pathlib import Path
import pandas as pd
from investor.point_in_time import EvidenceItem,PointInTimeResearchEngine,PointInTimeSnapshotStore
from investor.v6 import BabyInvestorV6,PaperBroker,OutOfSampleEvaluator

with TemporaryDirectory() as td:
    eng=PointInTimeResearchEngine(PointInTimeSnapshotStore(Path(td)/"pit.db"))
    snaps=[]
    for date,score in [("2025-01-02T16:00:00+00:00",70),("2025-01-06T16:00:00+00:00",40)]:
        e=EvidenceItem("decision_seed",score,"TEST",available_at=date,authority="PRIMARY",status="PASS")
        snaps.append(eng.build_snapshot("TEST",date,date[:10],date[:10],[e]))

    def deterministic(snapshot):
        score=float(snapshot.evidence["decision_seed"].value)
        return {"score":score,"state":"CANDIDATE" if score>=60 else "WAIT",
                "confidence":90,"coverage":100,"risk_level":"LOW","hard_override":False}

    idx=pd.date_range("2025-01-02",periods=6,freq="B")
    prices={"TEST":pd.DataFrame({"Close":[100,101,102,103,104,105]},index=idx)}
    out=BabyInvestorV6(deterministic).run(snaps,prices,str(idx[0].date()),str(idx[-1].date()),cost_bps=5,universe_coverage=.75)
    assert out["audit"]["lookahead_violations"]==0
    assert out["audit"]["survivorship_status"]=="INCOMPLETE"
    assert out["audit"]["ai_scoring_authority"]==0
    assert out["audit"]["real_money_execution"]=="DISABLED"
    assert len(out["decisions"])==2

    broker=PaperBroker(Path(td)/"paper.db",starting_cash=10000,fee_bps=1)
    order=broker.submit("TEST","BUY",10)
    filled=broker.fill(order,100)
    assert filled.status=="FILLED"
    assert broker.portfolio.positions["TEST"]==10
    assert broker.portfolio.cash<9000
    sell=broker.submit("TEST","SELL",10)
    assert broker.fill(sell,110).status=="FILLED"
    assert broker.portfolio.positions["TEST"]==0

    oos=OutOfSampleEvaluator.summarize([
      {"status":"PASS","total_return":.10},{"status":"PASS","total_return":-.02}])
    assert oos["folds"]==2 and abs(oos["positive_fold_rate"]-.5)<1e-12

print("V6.0 integrated historical validation + paper trading contract: PASS")
print("historical deterministic replay: PASS")
print("next-bar portfolio simulation: PASS")
print("survivorship disclosure: PASS")
print("performance/OOS evaluation: PASS")
print("persistent local paper broker: PASS")
print("real-money execution disabled: PASS")
