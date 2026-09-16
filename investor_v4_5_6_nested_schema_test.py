import sys,types
if "yfinance" not in sys.modules:
 y=types.ModuleType("yfinance");y.download=lambda *a,**k:None;y.Ticker=type("T",(),{"__init__":lambda s,*a,**k:None,"info":{},"news":[]});sys.modules["yfinance"]=y
if "openai" not in sys.modules:
 o=types.ModuleType("openai");o.OpenAI=object;sys.modules["openai"]=o
from investor.committee.committee import NemotronInvestmentCommittee as C
from investor.integrity.claim_validator import ClaimValidator

safe,bad=C._sanitize_final_claims("CRWD is risky")
assert safe==[] and len(bad)==1
safe,bad=C._sanitize_final_claims([{"statement":"ok"},"bad member",7])
assert len(safe)==1 and len(bad)==2
safe,bad=C._sanitize_final_claims({"statement":"single"})
assert len(safe)==1 and bad==[]

# Direct validator must also never crash on non-dict members.
from investor.integrity.evidence_registry import EvidenceRegistry
v=ClaimValidator()
reg=EvidenceRegistry()
try:
 out=v.validate(["malformed string"],reg)
except AttributeError as e:
 raise AssertionError("ClaimValidator leaked malformed LLM type") from e

print("V4.5.6 nested-LLM-boundary contract: PASS")
print("string claims container quarantined: PASS")
print("mixed claims list quarantined: PASS")
print("single claim object normalized: PASS")
print("ClaimValidator second defense boundary: PASS")
