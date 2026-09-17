from __future__ import annotations
import json, sqlite3
from datetime import datetime, timezone
from pathlib import Path

def now():return datetime.now(timezone.utc).isoformat()
class MonitoringStore:
    def __init__(self,path='data/baby_monitoring.db'):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True);self._init()
    def db(self):
        d=sqlite3.connect(self.path);d.row_factory=sqlite3.Row;return d
    def _init(self):
        with self.db() as d:d.execute('CREATE TABLE IF NOT EXISTS alerts(id INTEGER PRIMARY KEY AUTOINCREMENT,symbol TEXT,severity TEXT,kind TEXT,payload TEXT,created_at TEXT,acknowledged INTEGER DEFAULT 0)');d.commit()
    def record(self,symbol,severity,kind,payload):
        with self.db() as d:d.execute('INSERT INTO alerts(symbol,severity,kind,payload,created_at) VALUES(?,?,?,?,?)',(symbol,severity,kind,json.dumps(payload,default=str),now()));d.commit()
    def evaluate_change(self,old,new):
        alerts=[]; symbol=new.get('symbol') or old.get('symbol')
        os=(old.get('decision') or {}).get('score'); ns=(new.get('decision') or {}).get('score')
        if os is not None and ns is not None and abs(float(ns)-float(os))>=5: alerts.append(('MEDIUM','SCORE_CHANGE',{'old':os,'new':ns}))
        oldrisk=(old.get('decision') or {}).get('hard_risk'); newrisk=(new.get('decision') or {}).get('hard_risk')
        if not oldrisk and newrisk: alerts.append(('CRITICAL','HARD_RISK_ACTIVATED',{}))
        oldstate=(old.get('thesis_state') or {}).get('state'); newstate=(new.get('thesis_state') or {}).get('state')
        if oldstate!=newstate and newstate in ('WEAKENING','BROKEN','BROKEN_OR_CONSTRAINED'): alerts.append(('HIGH','THESIS_DETERIORATION',{'old':oldstate,'new':newstate}))
        for sev,kind,p in alerts:self.record(symbol,sev,kind,p)
        return [{'symbol':symbol,'severity':a,'kind':b,'payload':c} for a,b,c in alerts]
