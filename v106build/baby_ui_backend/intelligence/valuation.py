from __future__ import annotations
from .common import metric,stage,num,safe_div

def reverse_dcf_required_growth(price,shares,fcf,net_cash=0,discount=.10,terminal=.03,years=5):
 price,shares,fcf,net_cash=map(num,(price,shares,fcf,net_cash))
 if None in (price,shares,fcf) or price<=0 or shares<=0 or fcf<=0 or discount<=terminal:return None
 target=price*shares-net_cash
 def pv(g):
  total=0.; x=fcf
  for y in range(1,years+1): x*=1+g; total+=x/(1+discount)**y
  terminal_value=x*(1+terminal)/(discount-terminal); return total+terminal_value/(1+discount)**years
 lo,hi=-.5,1.5
 if pv(lo)>target or pv(hi)<target:return None
 for _ in range(100):
  mid=(lo+hi)/2
  if pv(mid)<target:lo=mid
  else:hi=mid
 return (lo+hi)/2*100

def build_valuation(research,fundamentals,market_cap=None,price=None,shares=None):
 fm={m['key']:m.get('value') for m in fundamentals.get('metrics',[])}; mc=num(market_cap)
 fcf=num(fm.get('fcf')); ni=num(fm.get('net_income')); rev=num(fm.get('revenue')); net_cash=num(fm.get('net_cash')) or 0
 pe=safe_div(mc,ni); ps=safe_div(mc,rev); fcf_y=(100*fcf/mc) if mc and fcf else None
 rg=reverse_dcf_required_growth(price,shares,fcf,net_cash)
 ms=[metric('pe','P/E',pe,formula='Market Cap / Net Income',inputs={'market_cap':mc,'net_income':ni}),metric('ps','P/S',ps,formula='Market Cap / Revenue',inputs={'market_cap':mc,'revenue':rev}),metric('fcf_yield','FCF Yield',fcf_y,unit='%',formula='FCF / Market Cap × 100',inputs={'fcf':fcf,'market_cap':mc}),metric('reverse_dcf_growth','Reverse DCF Implied 5Y FCF Growth',rg,unit='%',formula='Growth rate that equates discounted FCF + terminal value to enterprise value',inputs={'price':price,'shares':shares,'fcf':fcf,'net_cash':net_cash,'discount_rate':10,'terminal_growth':3,'years':5})]
 return stage('valuation_v105','V10.5 Advanced Valuation & Expectations Engine',ms,summary='Valuation is scenario evidence, not a single objective fair value. Reverse DCF exposes expectations embedded in price.')
