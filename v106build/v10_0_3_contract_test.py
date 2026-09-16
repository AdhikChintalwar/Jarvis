from datetime import datetime, timezone
from baby_ui_backend.proposal_service import PaperProposalService
from baby_ui_backend.execution_quote import ExecutionQuoteService

svc=PaperProposalService(base_risk_percent=.5,max_position_percent=10,enforce_trade_quality=True,require_execution_grade=True,revalidate_setup=True,min_rr_target_1=1.0,min_rr_target_2=2.0)
portfolio={'account':{'equity':100000,'cash':100000}}

def research(setup='AT_PULLBACK_ZONE', risk='MODERATE', hard=False, decision='WATCH', t1=115, t2=125):
    return {'symbol':'TEST','decision':decision,'score':55,'confidence':70,'coverage':100,'risk':risk,'hard_risk_override':hard,
      'trade_plan':{'status':setup,'current_setup':{'status':setup},
        'pullback':{'entry_low':99,'entry_high':101,'planned_entry':100,'invalidation':95,'target_1':t1,'target_2':t2},
        'breakout':{'trigger':105,'invalidation':100,'target_1':115,'target_2':120},
        'position':{'unified_risk_multiplier':.8}}}

def q(price=100, eligible=True):
    return {'symbol':'TEST','price':price,'quality':'LIVE_IEX','provider':'ALPACA_MARKET_DATA','timestamp':datetime.now(timezone.utc).isoformat(),
            'execution_eligible':eligible,'validation_issues':[] if eligible else ['STALE_TIMESTAMP']}

# Good setup: 3R / 5R, execution grade, active zone.
p=svc.build('TEST',research(),q(),portfolio)
assert p['eligible'] is True and p['status']=='ELIGIBLE' and p['proposed_quantity'] is not None
assert p['rr_target_1']==3.0 and p['rr_target_2']==5.0

# SPY-like poor T1/T2 economics are blocked even when setup is active.
p=svc.build('TEST',research(t1=100.5,t2=105),q(),portfolio)
assert p['eligible'] is False and p['trade_quality_status']=='BLOCKED'
assert 'RR_TARGET_1_BELOW_MINIMUM' in p['gate_failures'] and p['proposed_quantity'] is None

# Active research setup + stale/non-execution quote remains research-only.
p=svc.build('TEST',research(),q(eligible=False),portfolio)
assert p['eligible'] is False and p['status']=='RESEARCH_SETUP_ONLY' and p['proposed_quantity'] is None

# Persisted pullback status is revalidated against current quote.
p=svc.build('TEST',research(),q(price=110),portfolio)
assert p['eligible'] is False and p['setup_status']=='WAIT_FOR_PULLBACK_OR_BREAKOUT' and p['proposed_quantity'] is None

# Hard risk always wins.
p=svc.build('TEST',research(risk='VERY_HIGH',hard=True),q(),portfolio)
assert p['eligible'] is False and 'UNIFIED_RISK_BLOCK' in p['gate_failures']

# Quote validator rejects secondary/delayed and malformed/wide Alpaca quotes.
class BadAlpaca:
    def current_quote(self,symbol,feed='iex'):
        return {'symbol':symbol,'price':100,'bid':90,'ask':110,'timestamp':datetime.now(timezone.utc).isoformat(),'quality':'LIVE_IEX','provider':'ALPACA_MARKET_DATA'}
class NoAlpaca:
    def current_quote(self,symbol,feed='iex'): raise RuntimeError('offline')
class Fallback:
    class X:
        __dict__={'symbol':'TEST','price':100,'quality':'DELAYED','provider':'YFINANCE_SECONDARY','timestamp':datetime.now(timezone.utc).isoformat()}
    def get(self,symbol): return self.X()

v=ExecutionQuoteService(alpaca=BadAlpaca(),fallback=Fallback()).get('TEST')
assert v['execution_eligible'] is False and 'WIDE_SPREAD' in v['validation_issues']
v=ExecutionQuoteService(alpaca=NoAlpaca(),fallback=Fallback()).get('TEST')
assert v['execution_eligible'] is False and 'NON_EXECUTION_PROVIDER' in v['validation_issues']

print('BABY V10.0.3 TRADE ELIGIBILITY HARDENING: PASS')
print('minimum R:R gates: PASS')
print('execution-grade quote gate: PASS')
print('current setup revalidation: PASS')
print('hard-risk override precedence: PASS')
print('blocked proposal quantity suppression: PASS')
print('secondary quote cannot authorize paper entry: PASS')
print('AI scoring authority: 0%')
print('AI execution authority: NONE')
print('real money: DISABLED')
