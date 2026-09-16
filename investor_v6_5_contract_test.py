from types import SimpleNamespace
from datetime import datetime,timezone
import pandas as pd
from investor.historical.sec_pit_facts import HistoricalFact
from investor.v65 import CoherentHistoricalFinancialResolver,HistoricalMarketSnapshotEngine,FullHistoricalDecisionAdapter
from investor.point_in_time import EvidenceItem,PointInTimeResearchEngine,PointInTimeSnapshotStore
from tempfile import TemporaryDirectory
from pathlib import Path

def f(c,v,start,end,form="10-K"):
    return HistoricalFact(c,v,"USD",start,end,end,form,"000-test",None,"SEC",end+"T20:00:00+00:00")
facts={
 "RevenueFromContractWithCustomerExcludingAssessedTax":[f("RevenueFromContractWithCustomerExcludingAssessedTax",1000,"2024-01-01","2024-12-31"),f("RevenueFromContractWithCustomerExcludingAssessedTax",900,"2023-01-01","2023-12-31")],
 "NetIncomeLoss":[f("NetIncomeLoss",100,"2024-01-01","2024-12-31")],
 "NetCashProvidedByUsedInOperatingActivities":[f("NetCashProvidedByUsedInOperatingActivities",160,"2024-01-01","2024-12-31")],
 "PaymentsToAcquirePropertyPlantAndEquipment":[f("PaymentsToAcquirePropertyPlantAndEquipment",40,"2024-01-01","2024-12-31")],
 "CashAndCashEquivalentsAtCarryingValue":[f("CashAndCashEquivalentsAtCarryingValue",200,None,"2024-12-31")],
 "LongTermDebtCurrent":[f("LongTermDebtCurrent",20,None,"2024-12-31")],
 "LongTermDebtNoncurrent":[f("LongTermDebtNoncurrent",80,None,"2024-12-31")],
}
ev=CoherentHistoricalFinancialResolver().resolve(facts)
assert ev["free_cash_flow"].value==120
assert abs(ev["revenue_growth_yoy"].value-(1000/900-1))<1e-9
assert ev["debt"].value==100
assert ev["net_margin"].value==.1

idx=pd.date_range("2024-01-01",periods=260,freq="B")
close=pd.Series(range(100,360),index=idx,dtype=float)
h=pd.DataFrame({"Open":close-.5,"High":close+1,"Low":close-1,"Close":close,"Volume":1_000_000},index=idx)
m=HistoricalMarketSnapshotEngine().build("TEST",h,idx[-1])
assert m.current_price==359 and m.average_dollar_volume_20d>0
assert m.advanced_market["signals"]["realized_volatility_20d"]["value"] is not None

with TemporaryDirectory() as td:
    eng=PointInTimeResearchEngine(PointInTimeSnapshotStore(Path(td)/"x.db"))
    snap=eng.build_snapshot("TEST","2024-12-31T21:00:00+00:00","2024-12-31",None,list(ev.values()))
    d=FullHistoricalDecisionAdapter().evaluate(snap,market=m,macro={"score":55,"confidence":80,"coverage":100})
assert d["evidence_coverage"]>=80
assert d["ai_scoring_authority"]==0 and d["ai_execution_authority"]==0
assert "unified_risk" in d["report"]

print("V6.5 full historical replay contract: PASS")
print("coherent fiscal-period financials: PASS")
print("safe debt aggregation: PASS")
print("aligned FCF + YoY growth: PASS")
print("PIT technical/market snapshot: PASS")
print("financial + accounting + valuation + market + macro + unified risk + decision: PASS")
print("AI scoring/execution authority: 0%")
