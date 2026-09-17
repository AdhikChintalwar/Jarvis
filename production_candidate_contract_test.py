import os,tempfile
from investor.production import ProductionCandidate, PortfolioPolicy
from investor.production.historical import ProductionHistoricalValidator
from investor.production.monitoring import MonitoringStore

def ok(x,m):
    if not x: raise AssertionError(m)

with tempfile.TemporaryDirectory() as td:
    p=ProductionCandidate(td+'/prod.db')
    s=p.startup();ok(s['status']=='PASS','startup');ok(s['real_money']=='DISABLED','real money');ok(s['ai_authority']['score']==0,'AI score')
    payload={'symbol':'NVDA','entry':100,'qty':5}
    a=p.ledger.proposal('NVDA',payload,'same-key');b=p.ledger.proposal('NVDA',payload,'same-key');ok(not a['duplicate'] and b['duplicate'] and a['id']==b['id'],'idempotency')
    r=p.portfolio.evaluate(equity=100000,cash=50000,positions=[],candidate={'symbol':'NVDA','sector':'TECH'},proposed_notional=9000,proposed_risk=400);ok(r['eligible'],'portfolio pass')
    r2=p.portfolio.evaluate(equity=100000,cash=50000,positions=[],candidate={'symbol':'NVDA','sector':'TECH'},proposed_notional=20000,proposed_risk=400);ok(not r2['eligible'] and 'MAX_POSITION_PCT' in r2['failures'],'concentration')
    # V12 portfolio production guardrails
    r3=p.portfolio.evaluate(
        equity=100000,cash=50000,positions=[],
        candidate={'symbol':'AAPL','sector':'Technology'},
        proposed_notional=5000,proposed_risk=600)
    ok(not r3['eligible'] and r3['failures']==['MAX_SINGLE_TRADE_RISK'],'single trade risk')

    r4=p.portfolio.evaluate(
        equity=100000,cash=12000,positions=[],
        candidate={'symbol':'AAPL','sector':'Technology'},
        proposed_notional=5000,proposed_risk=300)
    ok(not r4['eligible'] and r4['failures']==['MIN_CASH_RESERVE'],'cash reserve')

    r5=p.portfolio.evaluate(
        equity=100000,cash=50000,
        positions=[{
            'symbol':'MSFT','quantity':10,'market_value':28000,
            'sector':'Technology','risk_dollars':500,
            'correlation_to_candidate':0.20
        }],
        candidate={'symbol':'AAPL','sector':'Technology'},
        proposed_notional=5000,proposed_risk=300)
    ok(not r5['eligible'] and r5['failures']==['MAX_SECTOR_PCT'],'sector concentration')

    r6=p.portfolio.evaluate(
        equity=100000,cash=50000,
        positions=[{
            'symbol':'MSFT','quantity':10,'market_value':32000,
            'sector':'Technology','risk_dollars':500,
            'correlation_to_candidate':0.85
        }],
        candidate={'symbol':'AAPL','sector':'Technology'},
        proposed_notional=5000,proposed_risk=300)
    ok(
        not r6['eligible']
        and 'MAX_SECTOR_PCT' in r6['failures']
        and 'MAX_CORRELATED_EXPOSURE' in r6['failures'],
        'correlated exposure'
    )

    r7=p.portfolio.evaluate(
        equity=100000,cash=50000,
        positions=[{
            'symbol':'MSFT','quantity':10,'market_value':10000,
            'sector':'Technology','risk_dollars':5900,
            'correlation_to_candidate':0.10
        }],
        candidate={'symbol':'AAPL','sector':'Consumer'},
        proposed_notional=5000,proposed_risk=300)
    ok(not r7['eligible'] and r7['failures']==['MAX_PORTFOLIO_RISK'],'portfolio risk')

    existing=p.portfolio.evaluate(
        equity=100000,cash=50000,
        positions=[{
            'symbol':'AAPL','quantity':10,'market_value':10000,
            'sector':'Technology','risk_dollars':200,
            'correlation_to_candidate':0.10
        }],
        candidate={'symbol':'AAPL','sector':'Technology'},
        proposed_notional=5000,proposed_risk=300)
    ok(
        existing['eligible']
        and 'EXISTING_POSITION_REQUIRES_RECONCILIATION' in existing['warnings'],
        'existing position reconciliation'
    )

    ten_positions=[
        {
            'symbol':f'TEST{i}',
            'quantity':1,
            'market_value':5000,
            'sector':f'Sector{i}',
            'risk_dollars':100,
            'correlation_to_candidate':0.10
        }
        for i in range(10)
    ]
    r8=p.portfolio.evaluate(
        equity=100000,cash=50000,positions=ten_positions,
        candidate={'symbol':'AAPL','sector':'Technology'},
        proposed_notional=5000,proposed_risk=300)
    ok(not r8['eligible'] and r8['failures']==['MAX_POSITIONS'],'max positions')

    missing=p.portfolio.evaluate(
        equity=None,cash=None,positions=[],candidate={},
        proposed_notional=None,proposed_risk=None)
    ok(
        not missing['eligible']
        and 'INVALID_EQUITY' in missing['failures']
        and 'MAX_POSITION_PCT' in missing['failures'],
        'missing portfolio evidence fails closed'
    )

    # V12 must be able to block a V11 candidate on portfolio risk
    blocked_v11={
        'symbol':'AAPL',
        'schema_version':'11.0.1',
        'decision':{
            'state':'CANDIDATE',
            'score':68,
            'confidence':72,
            'decision_grade_coverage':80,
            'constraints':[]
        },
        'trade_intelligence':{
            'setup_status':'AT_PULLBACK_ZONE',
            'entry_triggered':True,
            'paper_proposal':{
                'notional':15000,
                'risk_dollars':300,
                'sector':'Technology'
            },
            'position':{}
        },
        'thesis':{
            'hard_risk_override':False
        },
        'thesis_state':{
            'state':'STABLE'
        }
    }

    blocked_portfolio={
        'account':{
            'equity':100000,
            'cash':50000
        },
        'positions':[]
    }

    blocked_pd=p.decision.evaluate(blocked_v11,blocked_portfolio)

    ok(blocked_pd['status']=='BLOCKED','production decision blocked by portfolio')
    ok(not blocked_pd['portfolio_gate']['eligible'],'blocked production gate')
    ok('MAX_POSITION_PCT' in blocked_pd['portfolio_gate']['failures'],'blocked production reason')
    ok(blocked_pd['execution']=='NONE','blocked production execution')
    ok(blocked_pd['real_money']=='DISABLED','blocked production real money')

    etf=p.etf.evaluate('SPY',{'technical':{'metrics':{'price':600,'sma50':580,'sma200':550,'rsi14':60}},'macro_sector':{'regime':'RISK_ON'}});ok(etf['bull_weight']>0 and etf['fundamentals']=='NOT_APPLICABLE','ETF thesis')
    ex=p.positions.evaluate({'qty':10},{'invalidation':90,'target1':110,'target2':120},{'price':89,'hard_risk_override':False,'thesis_state':'STABLE'});ok(ex['action']=='EXIT_PROPOSAL' and ex['execution']=='EXPLICIT_CONFIRMATION_REQUIRED','exit proposal')
    ph=p.providers.assess({'SEC':{'configured':True,'authority':'PRIMARY'},'YAHOO':{'configured':True,'authority':'SECONDARY'}});ok(ph['status']=='PASS','provider health')
    ph2=p.providers.assess({'SEC':{'configured':True,'authority':'PRIMARY','error':'down'}});ok(ph2['fail_closed_for_execution'],'provider fail closed')
    m=MonitoringStore(td+'/mon.db');alerts=m.evaluate_change({'symbol':'X','decision':{'score':60,'hard_risk':False},'thesis_state':{'state':'STABLE'}},{'symbol':'X','decision':{'score':52,'hard_risk':True},'thesis_state':{'state':'BROKEN'}});ok(len(alerts)>=3,'monitoring')

# PIT fail closed using existing V11.5 lab
h=ProductionHistoricalValidator()
d=[{'symbol':'AAA','signal_time':'2025-01-02T20:00:00+00:00','score':70,'confidence':70,'coverage':70,'state':'CANDIDATE','evidence_available_at':'2025-01-03T20:00:00+00:00','market_available_at':'2025-01-02T20:00:00+00:00','universe_as_of':'2025-01-02T00:00:00+00:00'}]
bars=[{'symbol':'AAA','date':'2025-01-02','open':10,'high':11,'low':9,'close':10,'volume':1000},{'symbol':'AAA','date':'2025-01-03','open':10,'high':11,'low':9,'close':10.5,'volume':1000}]
out=h.run(d,bars,record=False);ok(out['metrics']['status']=='BLOCKED_PIT_VIOLATION','PIT fail closed')
print('BABY PRODUCTION CANDIDATE: PASS')
print('idempotent proposals                 PASS')
print('portfolio concentration/risk         PASS')
print('ETF-specific thesis                  PASS')
print('position exit proposals              PASS')
print('provider failure fail-closed         PASS')
print('monitoring/change alerts             PASS')
print('PIT lookahead fail-closed            PASS')
print('automatic production retuning        DISABLED')
print('AI scoring authority                 0%')
print('AI execution authority               NONE')
print('real-money execution                 DISABLED')
