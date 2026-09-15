import sys,types
yf=types.ModuleType("yfinance");yf.Ticker=lambda *a,**k:None;yf.download=lambda *a,**k:None
sys.modules.setdefault("yfinance",yf)
from types import SimpleNamespace
from datetime import datetime,timezone
from investor.sec_event_context import SECEventContextClassifier
from investor.event_intelligence import EventIntelligenceEngine

c=SECEventContextClassifier()
def f(context,form="10-Q",category="offering"):
 return SimpleNamespace(context=context,filing_form=form,category=category)

assert c.classify(f("The company completed a public offering and received net proceeds")).stage=="COMPLETED_TRANSACTION"
assert c.classify(f("We may issue securities in the future and such issuance may dilute holders")).stage=="RISK_DISCLOSURE"
assert c.classify(f("In 2024 we completed a public offering")).stage=="COMPLETED_TRANSACTION"  # completion exists in context
reg=c.classify(f("This shelf registration statement permits us to offer securities","S-3"))
assert reg.stage=="REGISTRATION" and not reg.actionable and reg.direction=="unknown"
mention=c.classify(f("Accounting treatment includes discussion of public offering costs"))
assert mention.stage=="MENTION" and not mention.actionable

now=datetime(2026,9,15,tzinfo=timezone.utc)
finding=SimpleNamespace(category="offering",phrase="public offering",filing_date="2026-09-01",
 filing_form="10-Q",filing_url="sec://x",context="Accounting treatment includes discussion of public offering costs")
r=EventIntelligenceEngine().analyze(SimpleNamespace(recent_filings=[]),[],SimpleNamespace(all_findings=[finding]),now=now)
e=r.events[0]
assert e.direction=="unknown"
assert ":MENTION" in e.event_type
assert r.negative_pressure==0

completed=SimpleNamespace(category="offering",phrase="public offering",filing_date="2026-09-01",
 filing_form="8-K",filing_url="sec://y",context="The company completed the public offering and received net proceeds of $50 million.")
rc=EventIntelligenceEngine().analyze(SimpleNamespace(recent_filings=[]),[],SimpleNamespace(all_findings=[completed]),now=now)
assert rc.events[0].direction=="negative"
assert ":COMPLETED_TRANSACTION" in rc.events[0].event_type
assert rc.negative_pressure>0 and rc.score<50

print("V3.9.1 SEC context validation: PASS")
print("mention:",e.event_type,e.direction,"pressure",r.negative_pressure)
print("completed:",rc.events[0].event_type,rc.events[0].direction,"score",rc.score)
