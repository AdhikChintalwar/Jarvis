from pathlib import Path
from tempfile import TemporaryDirectory
from datetime import datetime, timezone, timedelta
import json, threading, time

from baby_ui_backend.research_orchestrator import ResearchOrchestrator, ResearchOrchestrationError
from baby_ui_backend.v10_intelligence import V10IntelligenceService
from baby_ui_backend.proposal_service import PaperProposalService


def report(symbol='TEST', setup='WAIT_FOR_PULLBACK_OR_BREAKOUT'):
    return {
      'symbol':symbol,'decision':'WATCH','score':53.5,'confidence':73,'coverage':100,'risk':'MODERATE','hard_risk_override':False,'validation_status':'REVIEW',
      'research_completed_at':datetime.now(timezone.utc).isoformat(),
      'stages':[{'id':'technical','status':'PASS','metrics':[{'key':'price','value':100,'status':'PASS'}]}],
      'trade_plan':{'status':setup,'current_price':101,'market_data_as_of':'2026-09-16T00:00:00-04:00','market_data_source':'SECONDARY',
                    'current_setup':{'status':setup,'reason':'test'},
                    'pullback':{'planned_entry':95,'invalidation':90,'target_1':105,'target_2':115},
                    'breakout':{'trigger':103,'invalidation':98,'target_1':113,'target_2':118},'position':{'unified_risk_multiplier':.8}}
    }

class FakeResearch:
    def __init__(self, root, mode='ok'):
        self.root=Path(root); self.mode=mode; self.jobs={}; self.starts=0
    def start(self,symbol,force=False):
        self.starts+=1; self.jobs[symbol]={'symbol':symbol,'status':'RUNNING','stage':'research'}
        def work():
            time.sleep(.03)
            if self.mode=='fail': self.jobs[symbol]={'symbol':symbol,'status':'ERROR','stage':'Research failed','error':'synthetic failure'}; return
            self.root.mkdir(parents=True,exist_ok=True); (self.root/f'{symbol}.json').write_text(json.dumps(report(symbol)))
            self.jobs[symbol]={'symbol':symbol,'status':'READY','stage':'Complete'}
        threading.Thread(target=work,daemon=True).start(); return self.jobs[symbol]
    def status(self,symbol): return self.jobs.get(symbol,{'symbol':symbol,'status':'NOT_RESEARCHED'})

with TemporaryDirectory() as td:
    fake=FakeResearch(td); orch=ResearchOrchestrator(fake,td,max_age_seconds=3600,timeout_seconds=2,poll_seconds=.01)
    assert orch.inspect('NVDA').status=='MISSING'
    created=orch.ensure('NVDA'); assert created['action']=='CREATED' and created['status']=='FRESH' and fake.starts==1
    reused=orch.ensure('NVDA'); assert reused['action']=='REUSED' and fake.starts==1
    # Force stale using explicit completion timestamp.
    p=Path(td,'NVDA.json'); d=json.loads(p.read_text()); d['research_completed_at']=(datetime.now(timezone.utc)-timedelta(hours=2)).isoformat(); p.write_text(json.dumps(d))
    orch.max_age_seconds=60
    refreshed=orch.ensure('NVDA'); assert refreshed['action']=='REFRESHED' and fake.starts==2

    # Existing V10 invariants survive orchestration.
    r=json.loads(p.read_text()); quote={'price':102,'quality':'DELAYED','provider':'YFINANCE_SECONDARY','timestamp':datetime.now(timezone.utc).isoformat()}; portfolio={'account':{'equity':100000,'cash':100000}}
    proposal=PaperProposalService().build('NVDA',r,quote,portfolio); flow=V10IntelligenceService(td).full_flow('NVDA',quote,portfolio,proposal)
    assert flow['exit_policy']['entry'] is None and proposal['eligible'] is False

with TemporaryDirectory() as td:
    fake=FakeResearch(td,'fail'); orch=ResearchOrchestrator(fake,td,timeout_seconds=1,poll_seconds=.01)
    try: orch.ensure('FAIL')
    except ResearchOrchestrationError as e:
        payload=e.to_dict(); assert payload['status']=='RESEARCH_FAILED' and payload['stage']=='Research failed'
    else: raise AssertionError('failure was silently swallowed')

print('BABY V10.0.2 AUTO RESEARCH ORCHESTRATION: PASS')
print('missing research -> create: PASS')
print('fresh research -> reuse: PASS')
print('stale research -> refresh: PASS')
print('explicit research failure: PASS')
print('inactive setup safety invariant: PASS')
print('AI scoring authority: 0%')
print('AI execution authority: NONE')
print('real money: DISABLED')
