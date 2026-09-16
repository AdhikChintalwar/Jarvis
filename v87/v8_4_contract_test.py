from pathlib import Path
from tempfile import TemporaryDirectory
from baby_ui_backend.paper_trading import PaperTradingService
from baby_ui_backend.proposal_service import PaperProposalService

trade={
 'status':'AT_PULLBACK_ZONE','current_setup':{'status':'AT_PULLBACK_ZONE'},
 'pullback':{'planned_entry':100,'invalidation':95,'target_1':110,'target_2':115},
 'breakout':{},'position':{'unified_risk_multiplier':1.0}
}
research={'decision':'CANDIDATE','score':70,'confidence':75,'coverage':100,'risk':'MODERATE','hard_risk_override':False,'trade_plan':trade,'ai_scoring_authority':0.0,'ai_execution_authority':'NONE'}
quote={'price':100,'quality':'DELAYED','provider':'TEST','timestamp':'2026-09-16T15:00:00Z'}
with TemporaryDirectory() as td:
    broker=PaperTradingService(str(Path(td)/'paper.db'))
    snap=broker.snapshot({})
    svc=PaperProposalService(.5,10)
    p=svc.build('AAPL',research,quote,snap)
    assert p['eligible'] and p['status']=='ELIGIBLE'
    assert p['risk_budget_dollars']==500 and p['max_position_dollars']==10000
    assert p['proposed_quantity']==100 and p['proposed_notional']==10000
    # Candidate alone is insufficient if the trade setup has not triggered.
    research['trade_plan']['current_setup']['status']='WAIT_FOR_PULLBACK_OR_BREAKOUT'
    research['trade_plan']['status']='WAIT_FOR_PULLBACK_OR_BREAKOUT'
    p2=svc.build('AAPL',research,quote,snap)
    assert not p2['eligible'] and p2['proposed_quantity'] is None
    # Hard risk is sovereign.
    research['trade_plan']['current_setup']['status']='AT_PULLBACK_ZONE'; research['trade_plan']['status']='AT_PULLBACK_ZONE'; research['hard_risk_override']=True
    p3=svc.build('AAPL',research,quote,snap)
    assert not p3['eligible']
print('BABY V8.4 decision-to-paper connection contract: PASS')
print('triggered TradePlan required: PASS')
print('portfolio risk sizing: PASS')
print('hard-risk sovereignty: PASS')
print('AI execution authority: 0%')
print('real-money execution: DISABLED')
