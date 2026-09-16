import sys,types
if "yfinance" not in sys.modules:
 y=types.ModuleType("yfinance");y.download=lambda *a,**k:None;y.Ticker=type("T",(),{"__init__":lambda s,*a,**k:None,"info":{},"news":[]});sys.modules["yfinance"]=y
if "openai" not in sys.modules:
 o=types.ModuleType("openai");o.OpenAI=object;sys.modules["openai"]=o
from investor.committee.committee import NemotronInvestmentCommittee as C
class Fake:
 def __init__(self,repair_ok=True):self.calls=[];self.repair_ok=repair_ok
 def reason_json(self,**k):
  self.calls.append(k["task_name"])
  if "schema_repair" in k["task_name"]:
   return {"rankings":[{"symbol":"AAPL","rank":1,"committee_score":50,"decision":"WATCH","confidence":50,"claims":[]}]} if self.repair_ok else {"rankings":[]}
  return {"committee_summary":"valid JSON, wrong schema"}
f=Fake();c=C(f)
r=c._run_committee_resilient({"candidates":[{"symbol":"AAPL"}]},1,True)
assert r["rankings"][0]["symbol"]=="AAPL"
assert r["_schema_diagnostics"]["repair_attempted"] and r["_schema_diagnostics"]["repair_success"]
assert f.calls==["investment_committee_deep_v4_5","investment_committee_schema_repair_v4_5_5"]
assert not C._committee_schema_diagnostics({"rankings":[]})["valid"]
assert C._committee_schema_diagnostics({"rankings":[{"symbol":"AAPL"}]})["valid"]
print("V4.5.5 committee-schema recovery contract: PASS")
print("wrong schema detected: PASS")
print("single repair pass: PASS")
print("repaired rankings accepted: PASS")
