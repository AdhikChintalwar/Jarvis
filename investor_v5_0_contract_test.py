from pathlib import Path
from tempfile import TemporaryDirectory
import pandas as pd
from investor.point_in_time import *
from investor.point_in_time.universe import UniverseMembership

with TemporaryDirectory() as td:
    store=PointInTimeSnapshotStore(Path(td)/"pit.db")
    eng=PointInTimeResearchEngine(store=store)
    ev=[
      EvidenceItem("old_revenue",100,"SEC",period_end="2024-12-31",
                   filed_at="2025-02-15T00:00:00+00:00",available_at="2025-02-15T00:00:00+00:00",authority="PRIMARY"),
      EvidenceItem("future_revenue",200,"SEC",period_end="2025-12-31",
                   filed_at="2026-02-15T00:00:00+00:00",available_at="2026-02-15T00:00:00+00:00",authority="PRIMARY"),
    ]
    snap=eng.build_snapshot("TEST","2025-06-01T16:00:00+00:00","2025-06-01",
                            "2025-05-30",ev)
    assert "old_revenue" in snap.evidence
    assert "future_revenue" not in snap.evidence
    assert len(snap.provenance["blocked_future_evidence"])==1
    assert store.load("TEST","2025-06-01T16:00:00+00:00") is not None

u=PointInTimeUniverse([
    UniverseMembership("OLD","2020-01-01","2024-12-31"),
    UniverseMembership("NEW","2025-01-01",None),
])
assert u.contains("OLD","2024-06-01")
assert not u.contains("OLD","2025-06-01")
assert u.contains("NEW","2025-06-01")

idx=pd.date_range("2025-01-01",periods=5,freq="B")
p=pd.DataFrame({"Close":[100,110,121,133.1,146.41]},index=idx)
# Signal on first bar must NOT receive first->second-bar gain; it executes on next bar.
signals={idx[0]:{"TEST":1.0}}
r=PointInTimeBacktester().run({"TEST":p},signals,str(idx[0].date()),str(idx[-1].date()),
                               transaction_cost_bps=0)
assert r.audit.status=="PASS"
assert r.audit.lookahead_violations==0
assert r.trades[0]["date"]==str(idx[1].date())
# Bought at 110, ending 146.41 => 33.1%, not 46.41%.
assert abs(r.metrics["total_return"]-0.331)<1e-9, r.metrics

try:
    PointInTimeBacktester().run({"TEST":p},signals,str(idx[0].date()),str(idx[-1].date()),
                                point_in_time_universe=False)
    raise AssertionError("must reject survivor-biased universe")
except ValueError as e:
    assert "POINT_IN_TIME_UNIVERSE_REQUIRED" in str(e)

print("V5.0 point-in-time research/backtest contract: PASS")
print("future evidence blocked: PASS")
print("point-in-time universe membership: PASS")
print("next-bar execution / no same-close lookahead: PASS")
print("survivorship guard: PASS")
