import sys,types
if "yfinance" not in sys.modules:
 y=types.ModuleType("yfinance");y.download=lambda *a,**k:None;y.Ticker=type("T",(),{"__init__":lambda s,*a,**k:None,"info":{},"news":[]});sys.modules["yfinance"]=y
if "openai" not in sys.modules:
 o=types.ModuleType("openai");o.OpenAI=object;sys.modules["openai"]=o
from investor.committee.committee_guard import FinalCommitteeGuard,CommitteeGuardReport
from investor.committee.committee import NemotronInvestmentCommittee as C
from investor.committee.nemotron_client import NemotronClient as N

g=CommitteeGuardReport(deterministic_score=67.25,evidence_authority=80,module_coverage=100,maximum_decision="TOP_CANDIDATE")
out=FinalCommitteeGuard().apply(99,"TOP_CANDIDATE",99,100,g,deterministic_only=True)
assert out["final_score"]==67.25
assert out["llm_score"] is None
assert out["llm_weight"]==0.0
assert out["confidence"]==0.0

bad={"deliberations":[{"symbol":"AAPL","bull_claims":["bad"],"bear_claims":[],"contradictions":[]}]}
good={"deliberations":[{"symbol":"AAPL","bull_claims":[{"claim_id":"B1"}],"bear_claims":[],"contradictions":[]}]}
assert not N._cached_result_shape_valid("investment_deliberation_deep_v4_5",bad)
assert N._cached_result_shape_valid("investment_deliberation_deep_v4_5",good)

payload=[{"symbol":"AAPL","deterministic_committee_guard":{"deterministic_score":67.25,"maximum_decision":"TOP_CANDIDATE"}}]
fb=C._deterministic_provider_fallback(None,payload)
assert fb["_deterministic_only"] is True
assert fb["rankings"][0]["committee_score"]==67.25
print("V4.5.7 governance-hardening contract: PASS")
print("deterministic fallback exact baseline: PASS")
print("llm_score=None and llm_weight=0: PASS")
print("malformed deliberation cache rejected: PASS")
print("well-formed deliberation cache accepted: PASS")
