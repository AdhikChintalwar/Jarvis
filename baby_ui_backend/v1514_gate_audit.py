from __future__ import annotations
import json, os, sqlite3
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from fastapi import APIRouter, Query

STRUCTURAL={'INVALID_RISK_STRUCTURE','UNIFIED_RISK_BLOCK'}
REWARD_RISK={'RR_TARGET_1_BELOW_MINIMUM','RR_TARGET_2_BELOW_MINIMUM'}
EXECUTION={'EXECUTION_QUOTE_NOT_ELIGIBLE'}
DECISION_HARD={'DECISION_BLOCK:AVOID'}

def _failures(v):
    if not v: return []
    if isinstance(v,list): return [str(x) for x in v]
    try:
        x=json.loads(v)
        return [str(i) for i in x] if isinstance(x,list) else []
    except Exception:
        return [x.strip() for x in str(v).split(',') if x.strip()]

def classify_gate(g):
    g=str(g or '')
    if g in STRUCTURAL:return 'structural'
    if g in REWARD_RISK:return 'reward_risk'
    if g in EXECUTION:return 'execution'
    if g in DECISION_HARD:return 'decision'
    if g.startswith('SETUP_NOT_ACTIVE:') or g=='DECISION_BLOCK:WAIT':return 'timing'
    return 'other'

def near_ready_assessment(row):
    state=str(row.get('state') or '').upper()
    gates=_failures(row.get('failures_json'))
    cats={classify_gate(g) for g in gates}
    if state=='SETUP_READY':
        return {'derived_label':'SETUP_READY','near_ready':False,'paper_eligible':True,'informational_only':True,'blocker_categories':sorted(cats)}
    if state=='ACTIVE_SETUP' and 'structural' not in cats and 'decision' not in cats:
        return {'derived_label':'NEAR_READY','near_ready':True,'paper_eligible':False,'informational_only':True,'blocker_categories':sorted(cats)}
    return {'derived_label':state or 'MONITOR','near_ready':False,'paper_eligible':False,'informational_only':True,'blocker_categories':sorted(cats)}

class GateAuditService:
    def __init__(self, db_path=None):
        self.db_path=Path(db_path or os.getenv('BABY_UI_DB') or os.getenv('BABY_UI_DB_PATH') or 'data/baby_ui.db')
    def _connect(self):
        db=sqlite3.connect(self.db_path); db.row_factory=sqlite3.Row; return db
    def _table(self,db,n):
        return db.execute("select 1 from sqlite_master where type='table' and name=?",(n,)).fetchone() is not None
    def _rows(self,days):
        if not self.db_path.exists(): return []
        cutoff=(datetime.now(timezone.utc)-timedelta(days=days)).isoformat()
        with self._connect() as db:
            if self._table(db,'v1512_readiness_history'):
                return [dict(r) for r in db.execute("select * from v1512_readiness_history where observed_at>=? order by observed_at,id",(cutoff,)).fetchall()]
            if self._table(db,'v1511_readiness'):
                return [dict(r) for r in db.execute("select * from v1511_readiness where updated_at>=? order by updated_at",(cutoff,)).fetchall()]
        return []
    def overview(self,days=30):
        days=max(1,min(int(days),3650)); rows=self._rows(days)
        gates=Counter(); cats=Counter(); states=Counter(); latest={}
        for r in rows:
            sym=str(r.get('symbol') or '').upper(); states[str(r.get('state') or 'UNKNOWN').upper()]+=1
            if sym: latest[sym]=r
            for g in _failures(r.get('failures_json')):
                gates[g]+=1; cats[classify_gate(g)]+=1
        near=[]; blocked=[]
        for sym,r in latest.items():
            a=near_ready_assessment(r)
            item={'symbol':sym,'state':r.get('state'),'readiness_potential':r.get('readiness_potential'),'setup_status':r.get('setup_status'),'failures':_failures(r.get('failures_json')),**a}
            if a['near_ready']: near.append(item)
            elif str(r.get('state') or '').upper()=='ACTIVE_SETUP': blocked.append(item)
        near.sort(key=lambda x:(-(x.get('readiness_potential') or 0),x['symbol']))
        total=sum(gates.values())
        return {'status':'READY','feature':'V15.14_GATE_AUDIT','days':days,'authority':{'read_only':True,'changes_thresholds':False,'changes_execution':False,'near_ready_is_paper_eligible':False,'real_money_execution':'DISABLED'},'summary':{'observations':len(rows),'symbols':len(latest),'gate_hits':total,'setup_ready_observations':states.get('SETUP_READY',0),'active_setup_observations':states.get('ACTIVE_SETUP',0),'setup_forming_observations':states.get('SETUP_FORMING',0),'monitor_observations':states.get('MONITOR',0),'current_near_ready':len(near),'current_active_blocked':len(blocked)},'top_blocking_gates':[{'gate':g,'count':n,'category':classify_gate(g)} for g,n in gates.most_common(25)],'category_breakdown':[{'category':c,'count':n,'share_pct':round(n*100/total,1) if total else 0} for c,n in cats.most_common()],'current_near_ready':near,'current_active_blocked':blocked}
    def symbol(self,symbol,days=30):
        symbol=str(symbol or '').upper(); rows=[r for r in self._rows(days) if str(r.get('symbol') or '').upper()==symbol]
        current=rows[-1] if rows else None; gates=Counter()
        for r in rows:
            for g in _failures(r.get('failures_json')): gates[g]+=1
        return {'status':'READY','symbol':symbol,'days':days,'current':({**current,'failures':_failures(current.get('failures_json')),**near_ready_assessment(current)} if current else None),'top_blocking_gates':[{'gate':g,'count':n,'category':classify_gate(g)} for g,n in gates.most_common()],'history_count':len(rows),'authority':{'read_only':True,'near_ready_is_paper_eligible':False,'real_money_execution':'DISABLED'}}
    def plain_summary(self,days=30):
        o=self.overview(days); s=o['summary']; top=', '.join(f"{x['gate']} ({x['count']})" for x in o['top_blocking_gates'][:5]) or 'none'; nr=', '.join(x['symbol'] for x in o['current_near_ready'][:10]) or 'none'; return f"Over the last {days} days Baby recorded {s['observations']} readiness observations. Top blocking gates: {top}. Current derived NEAR_READY symbols: {nr}. NEAR_READY is informational only and is not PAPER eligible."

service=GateAuditService(); router=APIRouter(prefix='/api/v1514',tags=['V15.14 Gate Audit'])
@router.get('/health')
def health(): return {'status':'READY','feature':'V15.14_GATE_AUDIT','read_only':True,'thresholds_changed':False,'execution_changed':False,'real_money_execution':'DISABLED'}
@router.get('/gate-audit')
def gate_audit(days:int=Query(30,ge=1,le=3650)): return service.overview(days)
@router.get('/gate-audit/{symbol}')
def gate_audit_symbol(symbol:str,days:int=Query(30,ge=1,le=3650)): return service.symbol(symbol,days)
