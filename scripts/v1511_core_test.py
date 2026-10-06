import tempfile
from pathlib import Path
from baby_ui_backend.v1511_forward_validation import ForwardValidationLedger
from baby_ui_backend.v1511_readiness import classify
from baby_ui_backend.v1511_mobile_approval import MobileApprovalStore,validate_user_quantity
from baby_ui_backend.v1511_discovery import select_candidates

assert classify({'eligible':True,'status':'ELIGIBLE','setup_status':'AT_PULLBACK_ZONE'})['state']=='SETUP_READY'
assert classify({'eligible':False,'status':'RESEARCH_SETUP_ONLY','setup_status':'AT_PULLBACK_ZONE','trade_quality_status':'PASS','execution_quote_status':'BLOCKED','gate_failures':['EXECUTION_QUOTE_NOT_ELIGIBLE']})['state']=='NEAR_READY'
print('PASS readiness classification')

ok,reason,g=validate_user_quantity(5,{'quote_price':10,'entry_price':10,'invalidation':9.5},{'equity':10000,'cash':5000,'buying_power':5000})
assert ok and g['quantity']==5 and g['quantity_source']=='USER_SELECTED'
ok2,_,_=validate_user_quantity(5000,{'quote_price':10,'entry_price':10,'invalidation':9.5},{'equity':10000,'cash':5000,'buying_power':5000})
assert not ok2
print('PASS user quantity validation')

with tempfile.TemporaryDirectory() as td:
    db=str(Path(td)/'x.db')
    l=ForwardValidationLedger(db)
    r=l.record_ready('TEST',1,{
        'status':'ELIGIBLE',
        'eligible':True,
        'setup_status':'AT_PULLBACK_ZONE',
        'setup_type':'FLOW_ONLY',
        'entry_price':10,
        'quote_price':10,
        'invalidation':9,
        'target_1':11,
        'target_2':12
    })
    assert r and r['theoretical_outcome']=='OPEN'
    l.observe_price('TEST',11.1)
    row=l.list(1)[0]
    assert row['theoretical_outcome']=='T1_HIT'
    a=MobileApprovalStore(db);t=a.create('TEST',1,30);assert t and a.by_token(t)['status']=='PENDING'
print('PASS forward ledger and approval store')

rows=[
 {'symbol':'A','flow_score':50,'relative_volume':1.1},
 {'symbol':'B','flow_score':92,'relative_volume':1.8},
 {'symbol':'C','flow_score':75,'relative_volume':1.4,'breakout_20d':True},
 {'symbol':'D','flow_score':70,'relative_volume':2.5,'daily_change_pct':12,'current_dollar_volume':10000000},
]
out=select_candidates(rows,1)
assert out[0]['symbol']=='A' and {'B','C'}.issubset({x['symbol'] for x in out})
print('PASS diversified research discovery')
