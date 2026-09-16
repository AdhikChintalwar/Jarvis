import sys,types
from unittest.mock import patch
if "openai" not in sys.modules:
    op=types.ModuleType("openai");op.OpenAI=object;sys.modules["openai"]=op
if "yfinance" not in sys.modules:
    yf=types.ModuleType("yfinance")
    yf.download=lambda *a,**k:None
    yf.Ticker=type("Ticker",(),{"__init__":lambda self,*a,**k:None,"info":{},"news":[]})
    sys.modules["yfinance"]=yf
from investor.committee.nemotron_client import NemotronClient
class E503(Exception): status_code=503
assert NemotronClient.is_transient_provider_error(E503("503 overloaded"))
e=Exception("401 invalid key");e.status_code=401
assert not NemotronClient.is_transient_provider_error(e)

class Msg: content='{"ok": true}'
class Choice: message=Msg()
class Resp: choices=[Choice()]
class Creator:
    def __init__(self):self.n=0
    def create(self,**k):
        self.n+=1
        if self.n<3:raise E503("503 Service temporarily overloaded")
        return Resp()
creator=Creator()
comps=type("Comps",(),{})();comps.create=creator.create
chat=type("Chat",(),{})();chat.completions=comps
api=type("API",(),{})();api.chat=chat
c=object.__new__(NemotronClient);c.client=api;c.model="x";c.use_cache=False;c.cache_dir=__import__('pathlib').Path('/tmp/baby_v452_test_cache')
with patch("investor.committee.nemotron_client.time.sleep") as sleep:
    assert c.reason_json("s",{"x":1},"retry_test",retries=1)=={"ok":True}
    assert creator.n==3
    assert [x.args[0] for x in sleep.call_args_list]==[5,15]
print("V4.5.2 Nemotron reliability contract: PASS")
print("503 -> 5s -> 503 -> 15s -> success")
print("401 non-transient classification: PASS")
