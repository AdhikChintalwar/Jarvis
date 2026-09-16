import sys,types
if "yfinance" not in sys.modules:
 y=types.ModuleType("yfinance");y.download=lambda *a,**k:None;y.Ticker=type("T",(),{"__init__":lambda s,*a,**k:None,"info":{},"news":[]});sys.modules["yfinance"]=y
if "openai" not in sys.modules:
 o=types.ModuleType("openai");o.OpenAI=object;sys.modules["openai"]=o
from investor.committee.nemotron_client import NemotronClient

# Build parser instance without invoking network constructor.
n=object.__new__(NemotronClient)
truncated='{"deliberations":[{"symbol":"AAPL","bull_claims":[],"bear_claims":[],"contradictions":[]},{"symbol":"SLDE","bull_claims":[],"bear_claims":[],"contradictions":[]},{"symbol":"CRWD","bull_claims":['
r=n._parse_json(truncated)
assert r["_partial_response"] is True
assert len(r["deliberations"])==2
assert [x["symbol"] for x in r["deliberations"]]==["AAPL","SLDE"]

bad_nested={"deliberations":[{"symbol":"AAPL","bull_claims":["bad"],"bear_claims":[],"contradictions":[]}]}
assert not n._cached_result_shape_valid("investment_deliberation_recovery_v4_5_8",bad_nested)
print("V4.5.8 deep-reliability contract: PASS")
print("truncated deliberation partial-object recovery: PASS")
print("malformed recovery cache rejection: PASS")
