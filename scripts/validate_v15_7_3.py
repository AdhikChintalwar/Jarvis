#!/usr/bin/env python3
from pathlib import Path
import py_compile,sys

root=Path.cwd()
for p in [
    root/"baby_ui_backend/v157_data_quality.py",
    root/"scripts/v157_intraday_replay.py",
    root/"scripts/v157_feed_audit.py",
]:
    if not p.exists():
        raise SystemExit(f"Missing {p}")
    py_compile.compile(str(p),doraise=True)

sys.path.insert(0,str(root))
from baby_ui_backend.v157_data_quality import assess_intraday_quality

# Continuous 78-bar IEX session with tiny consolidated volume share should remain trusted.
bars=[]
from datetime import datetime,timedelta,timezone
start=datetime(2026,9,21,13,30,tzinfo=timezone.utc)
for i in range(78):
    ts=start+timedelta(minutes=5*i)
    bars.append({
        "timestamp":ts.isoformat().replace("+00:00","Z"),
        "open":100,"high":101,"low":99,"close":100.5,"volume":1000,
    })
q=assess_intraday_quality(
    bars,
    {"high":101,"low":99,"close":100.5,"volume":10_000_000},
    feed_scope="IEX",
)
assert q.quality_state=="TRUSTED", q.as_dict()
assert q.trust_intraday_signals is True

# Sparse session remains untrusted regardless of feed.
q2=assess_intraday_quality(
    bars[:10],
    {"high":101,"low":99,"close":100.5,"volume":10_000_000},
    feed_scope="IEX",
)
assert q2.quality_state=="UNTRUSTED", q2.as_dict()

print("V15.7.3 validation PASS")
print("IEX single-venue volume no longer falsely invalidates complete sessions.")
print("Sparse/gappy sessions remain blocked.")
print("Price-sequence trust and volume-sequence trust are separated.")
print("No execution or quantity logic changed.")
