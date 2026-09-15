import sys,types
yf=types.ModuleType("yfinance");yf.Ticker=lambda *a,**k:None;yf.download=lambda *a,**k:None
sys.modules.setdefault("yfinance",yf)
from types import SimpleNamespace
from datetime import datetime,timezone
from investor.event_intelligence import EventIntelligenceEngine

now=datetime(2026,9,15,tzinfo=timezone.utc)
filings=[
 SimpleNamespace(form="S-3",filing_date="2026-09-10",filing_url="sec://s3"),
 SimpleNamespace(form="4",filing_date="2026-09-12",filing_url="sec://4"),
 SimpleNamespace(form="8-K",filing_date="2026-09-14",filing_url="sec://8k"),
]
sec=SimpleNamespace(recent_filings=filings)
news=[
 {"title":"Company raises guidance after strong quarter","publisher":"Example News","providerPublishTime":1789344000},
 {"title":"Ordinary market commentary","publisher":"Example News","providerPublishTime":1789344000},
]
deep=SimpleNamespace(all_findings=[])
r=EventIntelligenceEngine().analyze(sec,news,deep,now=now)
assert r.primary_event_count==3
s3=next(e for e in r.events if e.filing_form=="S-3")
assert s3.direction=="unknown"
assert any("does not by itself prove" in n for n in s3.notes)
f4=next(e for e in r.events if e.filing_form=="4")
assert f4.direction=="unknown"
k8=next(e for e in r.events if e.filing_form=="8-K")
assert k8.direction=="unknown"
assert any(e.event_type=="guidance_raise" and e.direction=="positive" for e in r.events)
assert r.positive_pressure>0 and r.negative_pressure==0

# Old events decay and cannot remain permanent catalysts.
old=SimpleNamespace(recent_filings=[SimpleNamespace(form="8-K",filing_date="2024-01-01",filing_url="x")])
ro=EventIntelligenceEngine().analyze(old,[],SimpleNamespace(all_findings=[]),now=now)
assert ro.active_event_count==0

# SEC going-concern content is directional primary evidence.
finding=SimpleNamespace(category="going_concern",phrase="substantial doubt about going concern",
 filing_date="2026-09-14",filing_form="10-Q",filing_url="sec://gc")
rg=EventIntelligenceEngine().analyze(SimpleNamespace(recent_filings=[]),[],SimpleNamespace(all_findings=[finding]),now=now)
assert rg.negative_pressure>0
assert rg.score<50

print("V3.9 event-intelligence contract: PASS")
print("score:",r.score,"confidence:",r.confidence,"coverage:",r.coverage)
print("active:",r.active_event_count,"primary:",r.primary_event_count,"secondary:",r.secondary_event_count)
print("old active:",ro.active_event_count,"going-concern score:",rg.score)
