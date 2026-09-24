from pathlib import Path
from datetime import datetime,timezone
import sqlite3,json

def now():return datetime.now(timezone.utc).isoformat()
class V155PipelineStore:
    def __init__(self,path='data/baby_ui.db'):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True);self._init()
    def db(self):
        d=sqlite3.connect(self.path,timeout=30);d.row_factory=sqlite3.Row;return d
    def _init(self):
        with self.db() as d:d.executescript('''CREATE TABLE IF NOT EXISTS v155_pipeline_snapshots(id INTEGER PRIMARY KEY AUTOINCREMENT,symbol TEXT NOT NULL,stage TEXT NOT NULL,phase TEXT,setup_state TEXT,monitoring_signal TEXT,fingerprint TEXT NOT NULL,snapshot_json TEXT NOT NULL,created_at TEXT NOT NULL);CREATE INDEX IF NOT EXISTS idx_v155_symbol ON v155_pipeline_snapshots(symbol,id DESC);CREATE TABLE IF NOT EXISTS v155_alert_state(symbol TEXT NOT NULL,event_type TEXT NOT NULL,fingerprint TEXT NOT NULL,sent_at TEXT NOT NULL,PRIMARY KEY(symbol,event_type));''')
    def record(self,intel):
        x=intel.as_dict() if hasattr(intel,'as_dict') else dict(intel)
        with self.db() as d:d.execute('INSERT INTO v155_pipeline_snapshots(symbol,stage,phase,setup_state,monitoring_signal,fingerprint,snapshot_json,created_at) VALUES(?,?,?,?,?,?,?,?)',(x['symbol'],x['stage'],x.get('phase'),x.get('setup_state'),x.get('monitoring_signal'),x['fingerprint'],json.dumps(x,default=str,separators=(',',':')),now()));d.commit()
    def latest(self,symbol):
        with self.db() as d:r=d.execute('SELECT * FROM v155_pipeline_snapshots WHERE symbol=? ORDER BY id DESC LIMIT 1',(symbol.upper(),)).fetchone()
        if not r:return None
        x=dict(r);x['snapshot']=json.loads(x.pop('snapshot_json'));return x
    def recent(self,limit=100):
        with self.db() as d:rows=d.execute('SELECT id,symbol,stage,phase,setup_state,monitoring_signal,fingerprint,created_at FROM v155_pipeline_snapshots ORDER BY id DESC LIMIT ?',(min(max(int(limit),1),500),)).fetchall()
        return [dict(x) for x in rows]
    def summary(self,hours=24):
        with self.db() as d:rows=d.execute("SELECT stage,COUNT(*) n FROM v155_pipeline_snapshots WHERE created_at>=datetime('now',?) GROUP BY stage",(f'-{int(hours)} hours',)).fetchall()
        return {x['stage']:x['n'] for x in rows}
    def should_email(self,symbol,event,fingerprint):
        with self.db() as d:r=d.execute('SELECT fingerprint FROM v155_alert_state WHERE symbol=? AND event_type=?',(symbol.upper(),event)).fetchone()
        return not r or r['fingerprint']!=fingerprint
    def mark_email(self,symbol,event,fingerprint):
        with self.db() as d:d.execute('INSERT INTO v155_alert_state(symbol,event_type,fingerprint,sent_at) VALUES(?,?,?,?) ON CONFLICT(symbol,event_type) DO UPDATE SET fingerprint=excluded.fingerprint,sent_at=excluded.sent_at',(symbol.upper(),event,fingerprint,now()));d.commit()
