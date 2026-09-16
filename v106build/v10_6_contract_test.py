from baby_ui_backend.intelligence.platform import V106IntelligencePlatform
from baby_ui_backend.intelligence.valuation import reverse_dcf_required_growth

class FakeSEC:
 def companyfacts(self,s):
  def rows(vals):
   return {'units':{'USD':[{'val':v,'start':f'{y}-01-01','end':f'{y}-12-31','filed':f'{y+1}-02-01','form':'10-K','fy':y,'fp':'FY','accn':f'{y}-x'} for y,v in vals]}}
  facts={'RevenueFromContractWithCustomerExcludingAssessedTax':rows([(2024,100),(2025,120)]),'NetIncomeLoss':rows([(2024,10),(2025,15)]),'NetCashProvidedByUsedInOperatingActivities':rows([(2024,20),(2025,25)]),'PaymentsToAcquirePropertyPlantAndEquipment':rows([(2024,5),(2025,6)]),'GrossProfit':rows([(2024,50),(2025,65)]),'OperatingIncomeLoss':rows([(2024,15),(2025,20)])}
  def instant(c,v): facts[c]={'units':{'USD':[{'val':v,'end':'2025-12-31','filed':'2026-02-01','form':'10-K','fy':2025,'fp':'FY','accn':'i'}]}}
  for c,v in [('CashAndCashEquivalentsAtCarryingValue',30),('Assets',200),('Liabilities',80),('StockholdersEquity',120),('LongTermDebtNoncurrent',20)]:instant(c,v)
  return {'facts':{'us-gaap':facts}}
class FakeLive:
 def news(self,s): return [{'headline':'Company reports earnings and raises guidance','source':'TestWire','published_at':'2026-01-01'}]
 def market_context(self): return {'spy_change_percent':1.0,'qqq_change_percent':1.2}
research={'stages':[{'id':'technical','metrics':[{'key':'price','value':100},{'key':'sma20','value':95},{'key':'sma50','value':90},{'key':'sma200','value':80},{'key':'rsi14','value':55},{'key':'atr14','value':3},{'key':'rvol','value':1.6}]},{'id':'macro','score':55},{'id':'sec','status':'PASS'}], 'trade_plan':{'current_price':100,'support_1':95,'support_2':90,'resistance_1':105,'resistance_2':110}}
p=V106IntelligencePlatform(FakeSEC(),FakeLive())
r=p.build('TEST',research,profile={'market_cap':300,'shares_outstanding':3,'sector':'Tech','industry':'Software'},options={'put_call_volume':.8,'implied_volatility':35},institutional={'ownership_percent':70},flow={'order_flow_signal':'NEUTRAL'})
assert r['status']=='READY' and r['schema_version']=='10.6'
st={x['id']:x for x in r['stages']}
assert st['fundamentals_v101']['coverage']>70
fm={m['key']:m['value'] for m in st['fundamentals_v101']['metrics']}
assert round(fm['revenue_growth_yoy'],2)==20.0 and fm['fcf']==19 and fm['net_cash']==10
assert st['technical_v102']['metrics'][0]['value']=='BULLISH'
assert st['events_v103']['events'][0]['event_type']=='EARNINGS'
assert st['macro_v104']['status']=='PASS'
assert any(m['key']=='reverse_dcf_growth' for m in st['valuation_v105']['metrics'])
assert st['institutional_v106']['status']=='PASS'
assert r['authority']['LLM_SCORING_AUTHORITY']=='0%' and r['authority']['REAL_MONEY']=='DISABLED'
print('BABY V10.1–V10.6 UNIFIED INTELLIGENCE CONTRACT: PASS')
print('V10.1 SEC/XBRL fundamentals: PASS')
print('V10.2 technical/volume/structure: PASS')
print('V10.3 news/catalyst/events: PASS')
print('V10.4 macro/sector/cross-asset: PASS')
print('V10.5 valuation/reverse DCF: PASS')
print('V10.6 institutional/options/order-flow UNKNOWN-safe: PASS')
print('AI scoring authority: 0%')
print('Real money: DISABLED')
