import sys, types
sys.modules.setdefault('yfinance', types.ModuleType('yfinance'))
from investor.v115 import HistoricalStrategyLab,StrategyConfig,ReplayDecision,PriceBar

def d(sym,t,score=70,avail=None,hard=False):
    return ReplayDecision(sym,t,score,80,80,'CANDIDATE',risk_level='LOW',setup='AT_PULLBACK_ZONE',hard_risk=hard,evidence_available_at=avail or t,market_available_at=avail or t,universe_as_of=avail or t)

dec=[d('AAA','2026-01-02T16:00:00'),d('AAA','2026-01-03T16:00:00',30),d('BBB','2026-01-03T16:00:00',80,hard=True)]
bars=[]
for s in ('AAA','BBB'):
    for i,(dt,p) in enumerate([('2026-01-02',100),('2026-01-03',102),('2026-01-04',105),('2026-01-05',104)]):bars.append(PriceBar(s,dt,p,p+1,p-1,p+.5,1000000))
lab=HistoricalStrategyLab()
r=lab.run(dec,bars,StrategyConfig(),record=False)
assert r.schema_version=='11.5'
assert r.metrics['eligible_signals']==1
assert r.trades and r.trades[0]['fill_date']=='2026-01-03' # T -> next bar
assert r.integrity['status']=='REVIEW' # completeness flags intentionally absent
assert r.calibration['policy']=='DIAGNOSTIC_ONLY_NO_AUTOMATIC_RETUNING'
assert r.walk_forward['test_set_used_for_selection'] is False
bad=[d('AAA','2026-01-02T16:00:00',avail='2026-01-03T09:00:00')]
r2=lab.run(bad,bars,record=False)
assert r2.metrics['status']=='BLOCKED_PIT_VIOLATION'
assert not r2.trades
print('BABY V11.5 HISTORICAL VALIDATION & STRATEGY LAB: PASS')
print('signal T -> next-bar execution: PASS')
print('PIT lookahead fail-closed: PASS')
print('hard-risk eligibility block: PASS')
print('walk-forward untouched-test contract: PASS')
print('automatic retuning: DISABLED')
print('AI execution authority: NONE')
