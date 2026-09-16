from tempfile import TemporaryDirectory
from pathlib import Path
from types import SimpleNamespace as NS
import pandas as pd
from investor.historical import *
from investor.point_in_time import PointInTimeSnapshotStore, PointInTimeBacktester
from investor.historical.sec_pit_facts import HistoricalFact

facts={
 "RevenueFromContractWithCustomerExcludingAssessedTax":[
   HistoricalFact("RevenueFromContractWithCustomerExcludingAssessedTax",1000,"USD","2024-01-01","2024-12-31","2025-02-15","10-K","A",None,available_at="2025-02-15T12:00:00+00:00")],
 "NetIncomeLoss":[HistoricalFact("NetIncomeLoss",100,"USD","2024-01-01","2024-12-31","2025-02-15","10-K","A",None,available_at="2025-02-15T12:00:00+00:00")],
 "NetCashProvidedByUsedInOperatingActivities":[HistoricalFact("NetCashProvidedByUsedInOperatingActivities",150,"USD","2024-01-01","2024-12-31","2025-02-15","10-K","A",None,available_at="2025-02-15T12:00:00+00:00")],
 "PaymentsToAcquirePropertyPlantAndEquipment":[HistoricalFact("PaymentsToAcquirePropertyPlantAndEquipment",30,"USD","2024-01-01","2024-12-31","2025-02-15","10-K","A",None,available_at="2025-02-15T12:00:00+00:00")],
}
r=HistoricalFinancialResolver().resolve(facts)
assert r["revenue"].value==1000
assert r["free_cash_flow"].value==120
assert r["revenue"].metadata["accession"]=="A"

idx=pd.date_range("2020-01-01",periods=800,freq="B")
folds=WalkForwardValidator().folds(idx)
assert len(folds)>=2
assert all(x.status=="OUT_OF_SAMPLE" for x in folds)

prices={"A":pd.DataFrame({"Close":range(100,900)},index=idx)}
mw=BenchmarkEngine.momentum(prices,idx[-1])
assert mw=={"A":1.0}

bt=PointInTimeBacktester().run(prices,{idx[0]:{"A":1.0}},str(idx[0].date()),str(idx[-1].date()),transaction_cost_bps=0)
audit=ValidationAudit().build(model_version="5.5",snapshots=[],folds=folds,backtest=bt)
assert audit["lookahead_violations"]==0
assert audit["status"]=="PASS"

print("V5.5 historical research & validation platform contract: PASS")
print("SEC accession provenance: PASS")
print("historical financial reconstruction: PASS")
print("walk-forward OOS folds: PASS")
print("benchmark engine: PASS")
print("validation audit: PASS")
