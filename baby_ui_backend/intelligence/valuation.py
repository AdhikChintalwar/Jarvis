from __future__ import annotations
from .common import metric,stage,num
def reverse_dcf_required_growth(price,shares,fcf,net_cash=0,discount=.10,terminal=.03,years=5):
 price,shares,fcf,net_cash=map(num,(price,shares,fcf,net_cash))
 if None in (price,shares,fcf) or price<=0 or shares<=0 or fcf<=0 or discount<=terminal:return None
 target=price*shares-net_cash
 def pv(g):
  total=0.;x=fcf
  for y in range(1,years+1):x*=1+g;total+=x/(1+discount)**y
  return total+x*(1+terminal)/(discount-terminal)/(1+discount)**years
 lo,hi=-.5,1.5
 if pv(lo)>target or pv(hi)<target:return None
 for _ in range(100):
  mid=(lo+hi)/2
  if pv(mid)<target:lo=mid
  else:hi=mid
 return (lo+hi)/2*100
def build_valuation(research,fundamentals,market_cap=None,price=None,shares=None):
 if fundamentals.get('status')=='NOT_APPLICABLE':
  return stage('valuation_v105','V10.5 Advanced Valuation & Expectations Engine',[],status='NOT_APPLICABLE',summary='Operating-company valuation is not applicable to this asset type.',warnings=['NOT_APPLICABLE_ASSET_TYPE'])
 fm={m['key']:m.get('value') for m in fundamentals.get('metrics',[])};mc=num(market_cap);ni=num(fm.get('net_income'));rev=num(fm.get('revenue'));fcf=num(fm.get('fcf'));nc=num(fm.get('net_cash')) or 0
 raw_pe=mc/ni if mc and ni and ni>0 else None;pe=raw_pe if raw_pe is not None and raw_pe<=500 else None;ps=mc/rev if mc and rev and rev>0 else None;fy=100*fcf/mc if mc and fcf is not None else None;rg=reverse_dcf_required_growth(price,shares,fcf,nc)
 pe_status='PASS' if pe is not None else ('NOT_MEANINGFUL_EARNINGS_BASE' if ni is not None else 'UNKNOWN')
 ms=[metric('pe_ttm','P/E (TTM/FY basis)',pe,formula='Market Cap / positive aligned Net Income',inputs={'market_cap':mc,'net_income':ni},status=pe_status),metric('ps_ttm','P/S (TTM/FY basis)',ps,formula='Market Cap / aligned Revenue',inputs={'market_cap':mc,'revenue':rev}),metric('fcf_yield_ttm','FCF Yield (TTM/FY basis)',fy,unit='%',formula='Aligned FCF / Market Cap × 100',inputs={'fcf':fcf,'market_cap':mc}),metric('reverse_dcf_growth','Reverse DCF Implied 5Y FCF Growth',rg,unit='%',inputs={'price':price,'shares':shares,'fcf':fcf,'net_cash':nc,'discount_rate':10,'terminal_growth':3,'years':5})]
 w=[]
 if ni is not None and ni<=0:w.append('P/E is not meaningful because earnings are non-positive.')
 elif raw_pe is not None and raw_pe>500:w.append('P/E suppressed: positive earnings base is too small for a useful multiple (>500x).')
 if fcf is None:w.append('FCF yield and reverse DCF blocked because aligned FCF is unavailable.')
 return stage('valuation_v105','V10.5 Advanced Valuation & Expectations Engine',ms,summary='Valuation uses temporally aligned TTM/FY denominators; non-meaningful multiples are suppressed.',warnings=w)
