from baby_ui_backend.intelligence.sec_fundamentals import build_fundamentals
from baby_ui_backend.intelligence.valuation import build_valuation
from baby_ui_backend.intelligence.events import build_events

def row(val,start,end,filed,form='10-Q',fp='Q2',fy=2026,accn='x'):
 d={'val':val,'start':start,'end':end,'filed':filed,'form':form,'fp':fp,'fy':fy,'accn':accn};return d

def facts(concepts):
 return {'facts':{'us-gaap':{k:{'units':{'USD':v}} for k,v in concepts.items()}}}
# Reproduce live defect: current OCF plus 2020-only capex must NEVER create FCF.
f=facts({
 'NetCashProvidedByUsedInOperatingActivities':[row(74_421_000_000,'2026-05-01','2026-07-31','2026-08-26')],
 'PaymentsToAcquirePropertyPlantAndEquipment':[row(372_000_000,'2020-05-01','2020-07-31','2020-08-19',fy=2020)],
})
r=build_fundamentals('NVDA',f);m={x['key']:x for x in r['metrics']}
assert m['fcf']['value'] is None, m['fcf']
assert m['fcf']['status'] in {'UNKNOWN','INVALID_PERIOD_ALIGNMENT'}
v=build_valuation({},r,market_cap=1e12,price=200,shares=5e9)
vm={x['key']:x for x in v['metrics']}
assert vm['fcf_yield_ttm']['value'] is None and vm['reverse_dcf_growth']['value'] is None
# Negative and tiny earnings cannot masquerade as useful P/E.
r2={'metrics':[{'key':'net_income','value':-10},{'key':'revenue','value':100},{'key':'fcf','value':5},{'key':'net_cash','value':0}]}
v2=build_valuation({},r2,market_cap=1000,price=10,shares=100); assert next(x for x in v2['metrics'] if x['key']=='pe_ttm')['value'] is None
r3={'metrics':[{'key':'net_income','value':1},{'key':'revenue','value':100},{'key':'fcf','value':5},{'key':'net_cash','value':0}]}
v3=build_valuation({},r3,market_cap=1000,price=10,shares=100); pe=next(x for x in v3['metrics'] if x['key']=='pe_ttm');assert pe['value'] is None and pe['status']=='NOT_MEANINGFUL_EARNINGS_BASE'
# Secondary news containing SEC is not a primary SEC event.
e=build_events('NVDA',[{'headline':'Peer SEC sector comparison','source':'test'}],{});assert e['events'][0]['event_type']=='GENERAL';assert e['coverage']==100 and e['event_count']==1
print('BABY V10.6.1 FINANCIAL TEMPORAL INTEGRITY: PASS')
print('2020 CapEx contamination regression: PASS')
print('FCF valuation propagation block: PASS')
print('negative/tiny earnings P/E semantics: PASS')
print('news/SEC classification separation: PASS')
