import sqlite3,json,hashlib
from pathlib import Path
from datetime import datetime,timezone
class ExperimentRegistry:
    def __init__(self,path='data/baby_v115_experiments.db'):
        self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True)
        with sqlite3.connect(self.path) as c:c.execute('CREATE TABLE IF NOT EXISTS experiments(id TEXT PRIMARY KEY,created_at TEXT,code_version TEXT,config TEXT,result TEXT,repro_hash TEXT)')
    def record(self,experiment_id,config,result,code_version='11.5'):
        raw=json.dumps({'config':config,'result':result},sort_keys=True,default=str); h=hashlib.sha256(raw.encode()).hexdigest()
        with sqlite3.connect(self.path) as c:c.execute('INSERT OR REPLACE INTO experiments VALUES(?,?,?,?,?,?)',(experiment_id,datetime.now(timezone.utc).isoformat(),code_version,json.dumps(config,sort_keys=True),json.dumps(result,sort_keys=True,default=str),h))
        return {'experiment_id':experiment_id,'reproducibility_hash':h,'database':str(self.path)}
