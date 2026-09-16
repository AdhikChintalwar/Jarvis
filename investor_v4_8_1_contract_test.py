import tempfile
from investor.providers.alpha_vantage_provider import AlphaVantageProvider
from investor.validation_engine import ValidationEngine
class Resp:
    def __init__(self,d): self.d=d
    def raise_for_status(self): pass
    def json(self): return self.d
class Session:
    def __init__(self): self.calls=0
    def get(self,*a,**k):
        self.calls+=1
        if self.calls==1:return Resp({"Information":"Please spread out free API requests more sparingly (1 request per second)."})
        return Resp({"Time Series (Daily)":{"2026-09-15":{"4. close":"100"}}})
with tempfile.TemporaryDirectory() as td:
    sleeps=[]; sess=Session()
    p=AlphaVantageProvider(api_key="fixture",cache_dir=td,min_request_interval_seconds=0,max_retries=2,
                           session=sess,sleep_fn=lambda x:sleeps.append(x))
    assert "Time Series (Daily)" in p._query("TIME_SERIES_DAILY","TEST","market")
    assert sess.calls==2 and sleeps
report={"primary_financial":{"verified_financials":{
"revenue":{"value":1000,"status":"PASS","confidence":.97},"net_income":{"value":100,"status":"PASS","confidence":.97},
"free_cash_flow":{"value":120,"status":"PASS","confidence":.97},"operating_cash_flow":{"value":150,"status":"PASS","confidence":.97},
"cash":{"value":200,"status":"PASS","confidence":.97},"debt":{"value":50,"status":"PASS","confidence":.97}}}}
ext={"source":"Alpha Vantage fixture","provider":"ALPHA_VANTAGE","independent":True,"status":"ACTIVE",
     "current_price":100.0,"market_as_of":"2026-09-15","financial_as_of":None}
v=ValidationEngine().validate(report,None,ext)
names={x["name"]:x for x in v.checks}
for k in ("revenue","net_income","operating_cash_flow","free_cash_flow","cash","debt"):
    assert names[f"external.{k}"]["status"]=="UNKNOWN"
assert v.coverage<100
print("V4.8.1 provider reliability + validation coverage contract: PASS")
print("validation:",v.status,v.score,"coverage",v.coverage,"P/R/F/U",v.checks_passed,v.checks_review,v.checks_failed,v.checks_unknown)
