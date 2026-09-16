import sys,types
if "yfinance" not in sys.modules:
    y=types.ModuleType("yfinance");y.download=lambda *a,**k:None
    y.Ticker=type("Ticker",(),{"__init__":lambda self,*a,**k:None,"info":{},"news":[]})
    sys.modules["yfinance"]=y
if "openai" not in sys.modules:
    o=types.ModuleType("openai");o.OpenAI=object;sys.modules["openai"]=o
from investor.committee.nemotron_client import NemotronClient as N
assert not N._cached_result_shape_valid("investment_committee_deep_v4_5",{"rankings":[]})
assert not N._cached_result_shape_valid("investment_committee_deep_v4_5",{"committee_summary":"stale"})
assert N._cached_result_shape_valid("investment_committee_deep_v4_5",{"rankings":[{"symbol":"AAPL"}]})
assert not N._cached_result_shape_valid("investment_deliberation_deep_v4_5",{"deliberations":[]})
assert N._cached_result_shape_valid("investment_deliberation_deep_v4_5",{"deliberations":[{"symbol":"AAPL"}]})
print("V4.5.4 cache-integrity contract: PASS")
print("empty/stale committee cache rejected: PASS")
print("valid committee cache accepted: PASS")
print("deliberation cache validation: PASS")
