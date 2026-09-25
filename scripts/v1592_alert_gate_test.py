from pathlib import Path
import sys
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from baby_ui_backend.v155_email import choose_event, build_email

def cur(stage='RESEARCH',phase='INSUFFICIENT_DATA',setup='INSUFFICIENT_DATA',flow='INSUFFICIENT_DATA',cat='NONE',signal='CONTINUE',ready=False):
    return NS(symbol='TWST',stage=stage,phase=phase,setup_state='WATCH',ready=ready,setup_type=setup,flow=NS(label=flow,rvol_20=2.1,dollar_volume=5000000,persistence_5=3,up_down_volume_ratio_5=1.6,weighted_clv_5=.25,retention_20=.72,atr_pct=4.1),catalyst=NS(event_type='NONE',strength=cat,source_tier='NONE',headline=None,source=None,published_at=None,causality='NOT_ESTABLISHED'),capital_risk=NS(level='LOW',reasons=[]),observed_facts=['Scanner opportunity score: 87.9.'],interpretation=['Research interpretation.'],contradicting_evidence=['No major contradiction detected.'],next_conditions=['Hold constructive flow.'],monitoring_signal=signal,evidence_score=58,fingerprint='abc123')

assert choose_event(cur(),None) is None
print('PASS insufficient_data_first_observation_silent')
assert choose_event(cur(stage='RESEARCH',phase='ACCUMULATION',setup='ACCUMULATION_SWING',flow='CONSTRUCTIVE'),None) is None
print('PASS early_research_silent')
x=cur(stage='MONITOR',phase='ACCUMULATION',setup='ACCUMULATION_SWING',flow='CONSTRUCTIVE')
assert choose_event(x,None)=='NEW_RESEARCH_CANDIDATE'
print('PASS researched_monitor_candidate_alerts')
assert choose_event(cur(stage='MONITOR',phase='ACCUMULATION',setup='ACCUMULATION_SWING',flow='CONSTRUCTIVE',signal='DATA_ISSUE'),None) is None
print('PASS initial_data_issue_silent')
prev={'stage':'MONITOR','monitoring_signal':'CONTINUE','catalyst':{}}
assert choose_event(cur(stage='MONITOR',phase='ACCUMULATION',setup='ACCUMULATION_SWING',flow='CONSTRUCTIVE',signal='DATA_ISSUE'),prev)=='DATA_ISSUE'
print('PASS existing_data_issue_alerts')

# Positive catalyst-event semantics remain available in choose_event.
# Company-specific filtering is enforced by SubscriberEmailService before send.
cat_cur=cur(
    stage='MONITOR',
    phase='ACCUMULATION',
    setup='ACCUMULATION_SWING',
    flow='MIXED',
    cat='HIGH'
)
cat_cur.catalyst.headline='Twist Bioscience announces strategic collaboration'
assert choose_event(cat_cur,prev)=='CATALYST_UPDATE'
print('PASS catalyst_update_semantics_preserved')
paper={'quote_price':10.42,'spread_pct':0.38,'quote_age_seconds':12,'entry_price':10.40,'invalidation':9.92,'target_1':11.20,'target_2':11.85,'rr_target_1':1.67,'rr_target_2':3.02}
subject,text,html=build_email(x,'NEW_RESEARCH_CANDIDATE',{'market_regime':'RISK_ON'},'Twist Bioscience Corporation',paper)
assert 'TWST (Twist Bioscience Corporation)' in subject
assert 'TWST — Twist Bioscience Corporation' in text
assert 'TWST — Twist Bioscience Corporation' in html
assert 'Current quote: $10.42.' in text
assert 'Planned entry: $10.40.' in text
assert 'Invalidation: $9.92.' in text
assert 'Target 1: $11.20.' in text
assert 'Quantity is USER_SELECTED' in text
assert 'NOT_ESTABLISHED' in text
for forbidden in ('account balance','paper cash','suggested shares','risk dollars'):
    assert forbidden.lower() not in text.lower()
print('PASS company_and_plan_rendering')
print('PASS sensitive_fields_omitted')
print('V15.9.2 alert-gate regression PASS')
