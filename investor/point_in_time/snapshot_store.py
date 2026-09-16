import json, sqlite3
from pathlib import Path
from typing import Optional
from .models import ResearchSnapshot, EvidenceItem

class PointInTimeSnapshotStore:
    def __init__(self, path="data/baby_point_in_time.db"):
        self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True)
        self.db=sqlite3.connect(self.path)
        self.db.execute("""CREATE TABLE IF NOT EXISTS research_snapshots(
            symbol TEXT NOT NULL, as_of TEXT NOT NULL, payload TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(symbol,as_of))""")
        self.db.commit()

    def save(self,s:ResearchSnapshot):
        self.db.execute("INSERT OR REPLACE INTO research_snapshots(symbol,as_of,payload) VALUES(?,?,?)",
                        (s.symbol.upper(),s.as_of,json.dumps(s.to_dict(),default=str)))
        self.db.commit()

    def load(self,symbol,as_of)->Optional[ResearchSnapshot]:
        row=self.db.execute("SELECT payload FROM research_snapshots WHERE symbol=? AND as_of=?",
                            (symbol.upper(),as_of)).fetchone()
        if not row:return None
        d=json.loads(row[0])
        ev={k:EvidenceItem(**v) for k,v in d.pop("evidence").items()}
        return ResearchSnapshot(evidence=ev,**d)
