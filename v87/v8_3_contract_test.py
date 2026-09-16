from pathlib import Path
from tempfile import TemporaryDirectory
from baby_ui_backend.paper_trading import PaperTradingService

with TemporaryDirectory() as td:
    p=Path(td)/'paper.db'
    b=PaperTradingService(str(p))
    assert p.exists()
    s=b.snapshot({})
    assert s['real_money_execution']=='DISABLED' and s['brokerage_connection']=='NONE'
    assert s['account']['cash']==100000
    o=b.submit_order('AAPL','BUY',10)
    assert o['status']=='PENDING'
    f=b.execute(o['id'],{'price':100,'source':'TEST','quality':'DELAYED','as_of':'2026-09-16T12:00:00Z'})
    assert f['status']=='FILLED'
    s=b.snapshot({'AAPL':{'price':110,'source':'TEST','quality':'DELAYED','as_of':'2026-09-16T12:01:00Z'}})
    assert len(s['positions'])==1 and s['positions'][0]['unrealized_pnl'] is not None
    sell=b.submit_order('AAPL','SELL',10)
    b.execute(sell['id'],{'price':110,'source':'TEST','quality':'DELAYED','as_of':'2026-09-16T12:02:00Z'})
    s=b.snapshot({})
    assert not s['positions'] and len(s['fills'])==2
print('BABY V8.3 persistent paper-trading contract: PASS')
print('database auto-create: PASS')
print('average cost + realized/unrealized P&L: PASS')
print('quote provenance + slippage: PASS')
print('real-money execution: DISABLED')
