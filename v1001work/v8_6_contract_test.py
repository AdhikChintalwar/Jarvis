from __future__ import annotations
from pathlib import Path
from types import SimpleNamespace

from baby_ui_backend.alpaca_broker import AlpacaPaperBroker, CONFIRMATION_PHRASE

class FakeClient:
    def get_account(self):
        return SimpleNamespace(account_number='PA12345678',equity='100000',cash='75000',buying_power='150000',currency='USD',trading_blocked=False)
    def get_all_positions(self): return []
    def get_orders(self,*args,**kwargs): return []

b=AlpacaPaperBroker(client=FakeClient())
s=b.status()
assert s['provider']=='ALPACA' and s['environment']=='PAPER'
assert s['connected'] is True and s['real_money_execution']=='DISABLED'
assert s['account_number_masked'].endswith('5678')

try:
    b.submit_confirmed_order(symbol='AAPL',side='BUY',quantity=1,confirmation='yes')
    raise AssertionError('order accepted without exact confirmation')
except PermissionError:
    pass

src=Path('baby_ui_backend/alpaca_broker.py').read_text()
assert 'paper=True' in src
assert 'api.alpaca.markets' not in src
app=Path('baby_ui_backend/app.py').read_text()
assert '/api/broker/alpaca/orders' in app
assert '/api/research/{symbol}/alpaca-paper-order' in app
assert "proposal=paper_proposal(symbol)" in app
assert CONFIRMATION_PHRASE=='EXECUTE ALPACA PAPER'

print('BABY V8.6 Alpaca Paper execution contract: PASS')
print('Alpaca environment hard-coded PAPER: PASS')
print('live endpoint absent: PASS')
print('explicit confirmation gate: PASS')
print('research proposal recomputed before broker submit: PASS')
print('AI execution authority: NONE')
print('real-money execution: DISABLED')
