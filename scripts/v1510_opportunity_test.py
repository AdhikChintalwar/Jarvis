#!/usr/bin/env python3
from unittest.mock import patch
import baby_ui_backend.v1510_opportunity as o
from baby_ui_backend.v155_intelligence import Intelligence, Flow, Catalyst, CapitalRisk

def fake_intel(cap='LOW', phase='INSUFFICIENT_DATA', flow='INSUFFICIENT_DATA', stage='RESEARCH', ready=False, setup_state='BLOCKED'):
    return Intelligence(symbol='TEST',stage=stage,phase=phase,setup_state=setup_state,ready=ready,setup_type='INSUFFICIENT_DATA',flow=Flow(label=flow),catalyst=Catalyst(),capital_risk=CapitalRisk(cap,[]),observed_facts=[],interpretation=[],contradicting_evidence=[],next_conditions=[],monitoring_signal='CONTINUE',evidence_score=30,fingerprint='old')

strong={'symbol':'TEST','price':10.0,'opportunity_score':82,'flow_score':91,'flow_type':'STRONG_ACCUMULATION','relative_volume':2.1,'rvol_3d_average':2.0,'high_volume_days_5d':3,'close_location_pct':82,'current_dollar_volume':25000000,'breakout_20d':True,'atr_pct':6.0,'daily_change_pct':4.0,'gap_pct':1.0,'up_down_volume_ratio_20d':2.2,'distance_ema20_pct':8.0}
weak={'symbol':'TEST','price':10.0,'opportunity_score':45,'flow_score':40,'flow_type':'NEUTRAL','relative_volume':0.8,'rvol_3d_average':0.9,'high_volume_days_5d':0,'close_location_pct':40,'current_dollar_volume':2000000,'breakout_20d':False}

class MemStore:
    def __init__(self,*a,**k): pass
    def record(self,*a,**k): pass
    def recent(self,*a,**k): return []

with patch.object(o,'OpportunityTrajectoryStore',MemStore):
    with patch.object(o,'_base_analyze',lambda *a,**k: fake_intel()):
        x=o.analyze('TEST',strong,{}, {})
        assert x.stage=='MONITOR' and x.setup_state=='BLOCKED' and x.ready is False and x.flow.label=='STRONG' and x.setup_type=='BREAKOUT'
        print('PASS strong_scanner_promotes_monitor_only')
    with patch.object(o,'_base_analyze',lambda *a,**k: fake_intel(cap='HIGH')):
        x=o.analyze('TEST',strong,{}, {})
        assert x.stage=='RESEARCH' and x.setup_state=='BLOCKED' and x.ready is False
        print('PASS high_capital_risk_not_promoted')
    with patch.object(o,'_base_analyze',lambda *a,**k: fake_intel()):
        x=o.analyze('TEST',weak,{}, {})
        assert x.stage=='RESEARCH' and x.ready is False
        print('PASS weak_scanner_stays_research')
    with patch.object(o,'_base_analyze',lambda *a,**k: fake_intel(phase='RE_ACCUMULATION',flow='CONSTRUCTIVE',stage='MONITOR')):
        x=o.analyze('TEST',strong,{}, {})
        assert x.phase=='RE_ACCUMULATION' and x.stage=='MONITOR'
        print('PASS existing_non_insufficient_intelligence_unchanged')
print('V15.10.0 opportunity-capture tests PASS')
