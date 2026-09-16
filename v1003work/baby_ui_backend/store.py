from __future__ import annotations
import json, sqlite3
from pathlib import Path
from datetime import datetime, timezone

class AlertStore:
    def __init__(self, path='data/baby_ui.db'):
        self.path=Path(path); self.path.parent.mkdir(parents=True, exist_ok=True); self._init()
    def _db(self): return sqlite3.connect(self.path)
    def _init(self):
        with self._db() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS alerts(id INTEGER PRIMARY KEY AUTOINCREMENT, dedupe_key TEXT, symbol TEXT, severity TEXT, title TEXT, message TEXT, payload TEXT, created_at TEXT, read_at TEXT)''')
            db.execute('CREATE INDEX IF NOT EXISTS idx_alert_dedupe ON alerts(dedupe_key,created_at)')
    def recent_duplicate(self,key,cutoff_iso):
        with self._db() as db:
            return db.execute('SELECT 1 FROM alerts WHERE dedupe_key=? AND created_at>=? LIMIT 1',(key,cutoff_iso)).fetchone() is not None
    def add(self, alert):
        now=datetime.now(timezone.utc).isoformat()
        with self._db() as db:
            cur=db.execute('INSERT INTO alerts(dedupe_key,symbol,severity,title,message,payload,created_at) VALUES(?,?,?,?,?,?,?)',(alert['dedupe_key'],alert.get('symbol'),alert['severity'],alert['title'],alert['message'],json.dumps(alert.get('payload',{})),now))
            return cur.lastrowid
    def list(self,limit=100):
        with self._db() as db:
            db.row_factory=sqlite3.Row
            rows=db.execute('SELECT * FROM alerts ORDER BY id DESC LIMIT ?',(limit,)).fetchall()
            out=[]
            for r in rows:
                d=dict(r); d['payload']=json.loads(d['payload'] or '{}'); out.append(d)
            return out
