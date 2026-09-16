from baby_ui_backend.intelligence.sec_fundamentals import build_fundamentals
from baby_ui_backend.intelligence.valuation import build_valuation
from baby_ui_backend.intelligence.platform import V106IntelligencePlatform


def row(val,start,end,concept_form='10-K',filed='2026-02-25',accn='A',fy=2026,fp='FY'):
    return {'val':val,'start':start,'end':end,'form':concept_form,'filed':filed,'accn':accn,'fy':fy,'fp':fp}

def inst(val,end='2026-01-25',filed='2026-02-25',accn='A'):
    return {'val':val,'end':end,'form':'10-K','filed':filed,'accn':accn,'fy':2026,'fp':'FY'}

def facts(nodes):
    return {'facts':{'us-gaap':{k:{'units':{'USD':v}} for k,v in nodes.items()}}}

def metric_map(stage): return {m['key']:m for m in stage['metrics']}

# NVDA regression: stale preferred PP&E concept must lose to current-period ProductiveAssets.
nvda=facts({
 'Revenues':[row(215_938_000_000,'2025-01-27','2026-01-25')],
 'NetIncomeLoss':[row(120_067_000_000,'2025-01-27','2026-01-25')],
 'NetCashProvidedByUsedInOperatingActivities':[row(102_718_000_000,'2025-01-27','2026-01-25')],
 'PaymentsToAcquirePropertyPlantAndEquipment':[row(138_735_000,'2011-01-31','2012-01-29',filed='2012-03-01',accn='OLD',fy=2012)],
 'PaymentsToAcquireProductiveAssets':[row(6_100_000_000,'2025-01-27','2026-01-25',accn='NEW')],
 'CashAndCashEquivalentsAtCarryingValue':[inst(10_000_000_000)],
 'Assets':[inst(100_000_000_000)], 'Liabilities':[inst(30_000_000_000)], 'StockholdersEquity':[inst(70_000_000_000)],
})
s=build_fundamentals('NVDA',nvda); m=metric_map(s)
assert m['capex']['value']==6_100_000_000
assert m['capex']['inputs']['selected_concept']=='PaymentsToAcquireProductiveAssets'
assert m['capex']['inputs']['period_end']=='2026-01-25'
assert m['fcf']['value']==96_618_000_000 and m['fcf']['status']=='PASS'
assert m['fcf']['inputs']['capex_resolver']['selected_accession']=='NEW'

# CRWD regression: IncludingAssessedTax alias must resolve current annual revenue.
crwd=facts({
 'RevenueFromContractWithCustomerIncludingAssessedTax':[row(4_812_005_000,'2025-02-01','2026-01-31',filed='2026-03-15',accn='CRWD')],
 'NetIncomeLoss':[row(-162_502_000,'2025-02-01','2026-01-31',filed='2026-03-15',accn='CRWD')],
 'NetCashProvidedByUsedInOperatingActivities':[row(1_612_349_000,'2025-02-01','2026-01-31',filed='2026-03-15',accn='CRWD')],
 'PaymentsToAcquirePropertyPlantAndEquipment':[row(302_108_000,'2025-02-01','2026-01-31',filed='2026-03-15',accn='CRWD')],
})
s2=build_fundamentals('CRWD',crwd); m2=metric_map(s2)
assert m2['revenue']['value']==4_812_005_000
assert m2['revenue']['inputs']['selected_concept']=='RevenueFromContractWithCustomerIncludingAssessedTax'
v=build_valuation({},s2,market_cap=247_000_000_000,price=241,shares=1_000_000_000); vm=metric_map(v)
assert vm['pe_ttm']['value'] is None and vm['pe_ttm']['status']=='NOT_MEANINGFUL_EARNINGS_BASE'
assert vm['ps_ttm']['value'] is not None

# Stale-only CapEx remains blocked; never silently align by basis name alone.
stale=facts({
 'Revenues':[row(1000,'2025-01-01','2025-12-31')],
 'NetCashProvidedByUsedInOperatingActivities':[row(500,'2025-01-01','2025-12-31')],
 'PaymentsToAcquirePropertyPlantAndEquipment':[row(100,'2011-01-01','2011-12-31',filed='2012-02-01',fy=2011)],
})
s3=build_fundamentals('TEST',stale); m3=metric_map(s3)
assert m3['fcf']['value'] is None and m3['fcf']['status']=='INVALID_PERIOD_ALIGNMENT'

# ETF semantics: NOT_APPLICABLE, not a fake missing-company-data failure.
class NoSEC:
 def companyfacts(self,s): raise AssertionError('ETF must not call SEC Company Facts')
class NoLive:
 def news(self,s): return []
 def market_context(self): return {}
p=V106IntelligencePlatform(sec_provider=NoSEC(),live_provider=NoLive())
out=p.build('SPY',{'trade_plan':{'current_price':500}},news=[],market_context={},profile={'asset_type':'ETF','shares_outstanding':1})
fm=next(x for x in out['stages'] if x['id']=='fundamentals_v101')
val=next(x for x in out['stages'] if x['id']=='valuation_v105')
assert fm['status']=='NOT_APPLICABLE' and 'NOT_APPLICABLE_ETF' in fm['warnings'][0]
assert val['status']=='NOT_APPLICABLE'
assert out['release_version']=='10.6.2'

print('BABY V10.6.2 XBRL RESOLVER HARDENING: PASS')
print('NVDA stale-preferred-concept regression: PASS')
print('NVDA current-period CapEx alias selection: PASS')
print('CRWD revenue alias resolution: PASS')
print('period-alignment contamination block: PASS')
print('negative-earnings valuation semantics: PASS')
print('ETF NOT_APPLICABLE routing: PASS')
print('AI scoring authority: 0%')
print('real money: DISABLED')
