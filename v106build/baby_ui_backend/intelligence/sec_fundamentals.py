from __future__ import annotations
import json, os, time, urllib.request, urllib.parse
from pathlib import Path
from .common import Evidence, metric, stage, num, pct, safe_div

TICKERS='https://www.sec.gov/files/company_tickers.json'
FACTS='https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json'
CONCEPTS={
 'revenue':['RevenueFromContractWithCustomerExcludingAssessedTax','Revenues','SalesRevenueNet'],
 'net_income':['NetIncomeLoss','ProfitLoss'],
 'ocf':['NetCashProvidedByUsedInOperatingActivities'],
 'capex':['PaymentsToAcquirePropertyPlantAndEquipment','PaymentsForPropertyPlantAndEquipment'],
 'cash':['CashAndCashEquivalentsAtCarryingValue','CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents'],
 'assets':['Assets'],'liabilities':['Liabilities'],
 'equity':['StockholdersEquity','StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest'],
 'shares':['CommonStocksIncludingAdditionalPaidInCapitalMember','CommonStockSharesOutstanding'],
 'debt_current':['ShortTermBorrowings','LongTermDebtCurrent'],
 'debt_long':['LongTermDebtNoncurrent','LongTermDebt'],
 'gross_profit':['GrossProfit'],'operating_income':['OperatingIncomeLoss'],
}
DURATION={'revenue','net_income','ocf','capex','gross_profit','operating_income'}

class SecFundamentalProvider:
 def __init__(self,cache_dir='data/sec_cache',ttl=21600):
  self.cache=Path(cache_dir); self.cache.mkdir(parents=True,exist_ok=True); self.ttl=ttl
  self.ua=os.getenv('SEC_USER_AGENT','').strip()
 def _get(self,url,key):
  p=self.cache/f'{key}.json'
  if p.exists() and time.time()-p.stat().st_mtime<self.ttl:
   return json.loads(p.read_text())
  if not self.ua: raise RuntimeError('SEC_USER_AGENT is required for SEC automated access.')
  req=urllib.request.Request(url,headers={'User-Agent':self.ua,'Host':urllib.parse.urlparse(url).netloc})
  with urllib.request.urlopen(req,timeout=20) as r: data=json.loads(r.read().decode())
  tmp=p.with_suffix('.tmp'); tmp.write_text(json.dumps(data)); tmp.replace(p); return data
 def cik(self,symbol):
  data=self._get(TICKERS,'company_tickers')
  for x in data.values():
   if str(x.get('ticker','')).upper()==symbol.upper(): return int(x['cik_str'])
  return None
 def companyfacts(self,symbol):
  cik=self.cik(symbol)
  if cik is None: return None
  return self._get(FACTS.format(cik=cik),f'companyfacts_{cik:010d}')

def _entries(facts,concept):
 node=(facts.get('facts') or {}).get('us-gaap',{}).get(concept,{})
 units=node.get('units') or {}
 vals=[]
 for unit,rows in units.items():
  for r in rows:
   if r.get('form') not in {'10-K','10-Q','20-F','40-F'}: continue
   v=num(r.get('val'))
   if v is None: continue
   vals.append({**r,'val':v,'unit':unit,'concept':concept})
 return vals

def _latest(facts,names,duration=False):
 cand=[]
 for c in names:
  for r in _entries(facts,c):
   if duration and not r.get('start'): continue
   cand.append(r)
 if not cand:return None
 # filed/accession availability first, then period end. Prefer FY for duration; latest filing remains PIT-safe current evidence.
 cand.sort(key=lambda r:(r.get('filed',''),r.get('end',''),r.get('accn','')))
 return cand[-1]

def _annual_series(facts,names):
 cand=[]
 for c in names:
  for r in _entries(facts,c):
   if r.get('form') not in {'10-K','20-F','40-F'}: continue
   if not r.get('start'): continue
   cand.append(r)
 best={}
 for r in cand:
  end=r.get('end')
  if not end: continue
  prev=best.get(end)
  if prev is None or (r.get('filed',''),r.get('accn',''))>(prev.get('filed',''),prev.get('accn','')): best[end]=r
 return sorted(best.values(),key=lambda r:r.get('end',''))

def _yoy(facts,names):
 s=_annual_series(facts,names)
 return (pct(s[-1]['val'],s[-2]['val']),s[-1],s[-2]) if len(s)>=2 else (None,None,None)

def _ev(r):
 if not r:return []
 return [Evidence(r['val'],'SEC EDGAR Company Facts','PRIMARY',r.get('filed'),r.get('fy') and f"FY{r.get('fy')} {r.get('fp','')}",r.get('form'),r.get('accn'),verified=True,status='VERIFIED',concept=r.get('concept'))]

def build_fundamentals(symbol,facts):
 if not facts:return stage('fundamentals_v101','V10.1 Financial & Fundamental Intelligence',[],status='UNKNOWN',warnings=['SEC Company Facts unavailable.'])
 r={k:_latest(facts,v,k in DURATION) for k,v in CONCEPTS.items()}
 val={k:(x and x['val']) for k,x in r.items()}
 debt=(num(val['debt_current']) or 0)+(num(val['debt_long']) or 0) if val['debt_current'] is not None or val['debt_long'] is not None else None
 fcf=(num(val['ocf'])-abs(num(val['capex']))) if val['ocf'] is not None and val['capex'] is not None else None
 gross_margin=safe_div(val['gross_profit'],val['revenue']); op_margin=safe_div(val['operating_income'],val['revenue']); net_margin=safe_div(val['net_income'],val['revenue'])
 rev_yoy,rev_now,rev_prev=_yoy(facts,CONCEPTS['revenue']); ni_yoy,ni_now,ni_prev=_yoy(facts,CONCEPTS['net_income']); ocf_yoy,ocf_now,ocf_prev=_yoy(facts,CONCEPTS['ocf'])
 net_cash=(num(val['cash'])-debt) if val['cash'] is not None and debt is not None else None
 ms=[metric('revenue','Revenue',val['revenue'],unit=r['revenue'] and r['revenue']['unit'],evidence=_ev(r['revenue'])),
 metric('revenue_growth_yoy','Revenue Growth YoY',rev_yoy,unit='%',formula='(Latest annual revenue / prior annual revenue - 1) × 100',inputs={'latest':rev_now and rev_now['val'],'prior':rev_prev and rev_prev['val']},evidence=_ev(rev_now)+_ev(rev_prev)),
 metric('gross_margin','Gross Margin',gross_margin and gross_margin*100,unit='%',formula='Gross Profit / Revenue',inputs={'gross_profit':val['gross_profit'],'revenue':val['revenue']},evidence=_ev(r['gross_profit'])+_ev(r['revenue'])),
 metric('operating_margin','Operating Margin',op_margin and op_margin*100,unit='%',formula='Operating Income / Revenue',inputs={'operating_income':val['operating_income'],'revenue':val['revenue']},evidence=_ev(r['operating_income'])+_ev(r['revenue'])),
 metric('net_income','Net Income',val['net_income'],evidence=_ev(r['net_income'])),metric('net_margin','Net Margin',net_margin and net_margin*100,unit='%',formula='Net Income / Revenue',inputs={'net_income':val['net_income'],'revenue':val['revenue']},evidence=_ev(r['net_income'])+_ev(r['revenue'])),
 metric('net_income_growth_yoy','Net Income Growth YoY',ni_yoy,unit='%',formula='(Latest annual NI / prior annual NI - 1) × 100',inputs={'latest':ni_now and ni_now['val'],'prior':ni_prev and ni_prev['val']},evidence=_ev(ni_now)+_ev(ni_prev)),metric('ocf','Operating Cash Flow',val['ocf'],evidence=_ev(r['ocf'])),metric('ocf_growth_yoy','OCF Growth YoY',ocf_yoy,unit='%',formula='(Latest annual OCF / prior annual OCF - 1) × 100',inputs={'latest':ocf_now and ocf_now['val'],'prior':ocf_prev and ocf_prev['val']},evidence=_ev(ocf_now)+_ev(ocf_prev)),metric('capex','Capital Expenditure',val['capex'],evidence=_ev(r['capex'])),
 metric('fcf','Free Cash Flow',fcf,formula='OCF - abs(CapEx)',inputs={'ocf':val['ocf'],'capex':val['capex']},evidence=_ev(r['ocf'])+_ev(r['capex'])),
 metric('cash','Cash',val['cash'],evidence=_ev(r['cash'])),metric('debt','Total Debt',debt,formula='Current debt + long-term debt',inputs={'current':val['debt_current'],'long_term':val['debt_long']},evidence=_ev(r['debt_current'])+_ev(r['debt_long'])),
 metric('net_cash','Net Cash',net_cash,formula='Cash - Debt',inputs={'cash':val['cash'],'debt':debt},evidence=_ev(r['cash'])+_ev(r['debt_current'])+_ev(r['debt_long'])),
 metric('assets','Assets',val['assets'],evidence=_ev(r['assets'])),metric('liabilities','Liabilities',val['liabilities'],evidence=_ev(r['liabilities'])),metric('equity','Stockholders Equity',val['equity'],evidence=_ev(r['equity']))]
 return stage('fundamentals_v101','V10.1 Financial & Fundamental Intelligence',ms,summary='SEC/XBRL primary facts plus deterministic derived cash-flow, margin and leverage metrics.')
