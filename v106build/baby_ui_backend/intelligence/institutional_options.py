from __future__ import annotations
from .common import metric,stage

def build_institutional_options(options=None,institutional=None,flow=None):
 o=options or {}; i=institutional or {}; f=flow or {}
 ms=[metric('put_call_volume','Put/Call Volume Ratio',o.get('put_call_volume')),metric('put_call_oi','Put/Call Open Interest Ratio',o.get('put_call_oi')),metric('implied_volatility','Implied Volatility',o.get('implied_volatility'),unit='%'),metric('iv_rank','IV Rank',o.get('iv_rank')),metric('institutional_ownership','Institutional Ownership',i.get('ownership_percent'),unit='%'),metric('short_interest','Short Interest',i.get('short_interest_percent'),unit='%'),metric('dark_pool','Dark Pool / Off-exchange Signal',f.get('dark_pool_signal')),metric('order_flow','Order-flow Signal',f.get('order_flow_signal'))]
 warnings=[]
 if not any(m.get('value') is not None for m in ms):warnings=['No verified institutional/options/order-flow feed is configured. Baby refuses to infer these fields from price alone.']
 return stage('institutional_v106','V10.6 Institutional / Options / Order-Flow Intelligence',ms,summary='Advanced flow evidence is supplementary and never overrides hard risk or primary company facts.',warnings=warnings)
