from __future__ import annotations
from baby_ui_backend.alpaca_market import AlpacaMarketScreener
class LiveContextProvider:
 def __init__(self): self.market=AlpacaMarketScreener()
 def news(self,symbol,limit=20):
  try:
   x=self.market.news(symbols=[symbol],limit=limit)
   return x.get('news') or x.get('items') or [] if isinstance(x,dict) else (x or [])
  except Exception:return []
 def market_context(self):
  out={}
  for s in ['SPY','QQQ','DIA','IWM']:
   try:
    q=self.market.current_quote(s); out[s]=q
   except Exception:out[s]={}
  def ch(sym):
   q=out.get(sym) or {}; return q.get('change_percent') or q.get('percent_change')
  return {'spy_change_percent':ch('SPY'),'qqq_change_percent':ch('QQQ'),'snapshots':out,'source':'Alpaca Market Data','authority':'MARKET'}
