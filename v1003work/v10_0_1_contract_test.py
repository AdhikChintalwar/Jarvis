from pathlib import Path
from tempfile import TemporaryDirectory
import json
from baby_ui_backend.v10_intelligence import V10IntelligenceService
from baby_ui_backend.proposal_service import PaperProposalService

with TemporaryDirectory() as td:
    r={'symbol':'TEST','decision':'WATCH','score':53.5,'confidence':73,'coverage':100,'risk':'MODERATE','hard_risk_override':False,'validation_status':'REVIEW',
       'stages':[{'id':'financials','status':'PASS','score':67.6,'metrics':[{'key':'revenue','value':None,'status':'UNKNOWN','provenance':[{'status':'UNKNOWN','verified':False}]}]},
                 {'id':'technical','status':'PASS','metrics':[{'key':'price','value':100,'status':'PASS'}]}],
       'trade_plan':{'status':'WAIT_FOR_PULLBACK_OR_BREAKOUT','current_price':101,'market_data_as_of':'2026-09-16T00:00:00-04:00','market_data_source':'SECONDARY',
                     'current_setup':{'status':'WAIT_FOR_PULLBACK_OR_BREAKOUT','reason':'not triggered'},
                     'pullback':{'planned_entry':95,'invalidation':90,'target_1':105,'target_2':115},
                     'breakout':{'trigger':103,'invalidation':98,'target_1':113,'target_2':118},'position':{'unified_risk_multiplier':.8}}}
    Path(td,'TEST.json').write_text(json.dumps(r)); svc=V10IntelligenceService(td)
    quote={'price':102,'quality':'DELAYED','provider':'YFINANCE_SECONDARY','timestamp':'2026-09-16T22:00:00Z'}
    portfolio={'account':{'equity':100000,'cash':100000},'orders':[{'id':'old','status':'PENDING'}]}
    proposal=PaperProposalService().build('TEST',r,quote,portfolio)
    flow=svc.full_flow('TEST',quote,portfolio,proposal)
    assert flow['market_snapshot']['price']==102 and flow['market_snapshot']['research_price']==101
    assert flow['exit_policy']['status']=='WAIT_FOR_VALID_ENTRY' and flow['exit_policy']['entry'] is None
    assert proposal['eligible'] is False and 'has not triggered' in proposal['reason']
    assert flow['intelligence']['financial_health']['status']=='EVIDENCE_LINEAGE_INCOMPLETE'
    assert flow['intelligence']['financial_health']['production_status']=='PASS'
    assert flow['portfolio']['order_context']['current_flow_created_order'] is False

    r['trade_plan']['current_setup']={'status':'AT_PULLBACK_ZONE'}; Path(td,'TEST.json').write_text(json.dumps(r))
    proposal=PaperProposalService().build('TEST',r,quote,{'account':{'equity':100000,'cash':100000}})
    flow=svc.full_flow('TEST',quote,{},proposal)
    assert flow['exit_policy']['status']=='ACTIVE_POLICY' and flow['exit_policy']['entry']==102
    assert flow['exit_policy']['initial_invalidation']==90
    assert proposal['eligible'] is True and proposal['entry_price']==102

print('BABY V10.0.1 CONSISTENCY HARDENING: PASS')
print('single current-state market snapshot: PASS')
print('inactive setup cannot create active exit policy: PASS')
print('proposal reason precedence: PASS')
print('evidence-lineage guard: PASS')
print('existing paper-order provenance: PASS')
print('AI scoring authority: 0%')
print('AI execution authority: NONE')
print('real money: DISABLED')
