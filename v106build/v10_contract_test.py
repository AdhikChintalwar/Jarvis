from pathlib import Path
from tempfile import TemporaryDirectory
import json
from baby_ui_backend.v10_intelligence import V10IntelligenceService

with TemporaryDirectory() as td:
    r={
      'symbol':'TEST','decision':'CANDIDATE','score':67,'confidence':75,'coverage':90,'risk':'MODERATE','hard_risk_override':False,'validation_status':'PASS',
      'stages':[{'id':'financials','status':'PASS'},{'id':'valuation','status':'PASS'},{'id':'risk','status':'PASS'}],
      'trade_plan':{'current_setup':{'status':'AT_PULLBACK_ZONE'},'pullback':{'planned_entry':100,'invalidation':95,'target_1':110,'target_2':120}}
    }
    Path(td,'TEST.json').write_text(json.dumps(r))
    s=V10IntelligenceService(td); f=s.full_flow('TEST',quote={'price':100})
    assert f['research']['decision']=='CANDIDATE'
    assert f['exit_policy']['status']=='ACTIVE_POLICY'
    assert f['exit_policy']['rr_target_1']==2.0
    assert f['exit_policy']['rr_target_2']==4.0
    assert f['authority']['AI_SCORING']=='0%'
    assert f['authority']['REAL_MONEY']=='DISABLED'
    r['hard_risk_override']=True; Path(td,'TEST.json').write_text(json.dumps(r))
    assert s.full_flow('TEST')['warnings'][-1].startswith('Hard risk override')
print('BABY V10 INVESTMENT INTELLIGENCE: PASS')
print('research -> trade plan -> exit policy: PASS')
print('AI scoring authority: 0%')
print('AI execution authority: NONE')
print('real money: DISABLED')
