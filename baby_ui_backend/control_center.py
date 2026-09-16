from __future__ import annotations
import json, sqlite3
from pathlib import Path
from datetime import datetime, timezone
from typing import Any

ROOT=Path('.')

def _read_json(path:Path):
    try: return json.loads(path.read_text())
    except Exception: return None

def _first(d,*keys,default=None):
    cur=d
    for k in keys:
        if isinstance(cur,dict) and k in cur: cur=cur[k]
        else: return default
    return cur

def validation_summary(path='data/v7_5_real_investment_test.json'):
    p=Path(path)
    if not p.exists(): return {'status':'NOT_AVAILABLE','path':str(p)}
    d=_read_json(p) or {}
    perf=d.get('performance') or d.get('portfolio_performance') or d.get('metrics') or {}
    audit=d.get('audit') or {}
    benchmarks=d.get('benchmarks') or {}
    fills=d.get('fills') or d.get('trades') or []
    # tolerate V7/V7.5 report variants
    out={'status':'READY','path':str(p),'generated_at':d.get('generated_at'),'performance':perf,'benchmarks':benchmarks,
         'fills_count':len(fills) if isinstance(fills,list) else d.get('fills_count'), 'audit':audit,
         'survivorship_status': d.get('survivorship_status') or audit.get('survivorship_status') or audit.get('survivorship'),
         'warnings':d.get('warnings') or audit.get('warnings') or [], 'raw':d}
    return out

def _sqlite_tables(path:Path):
    if not path.exists(): return []
    try:
        with sqlite3.connect(path) as db:
            return [r[0] for r in db.execute("select name from sqlite_master where type='table' and name not like 'sqlite_%'")]
    except Exception:return []

def _rows(path:Path,table:str,limit=100):
    try:
        with sqlite3.connect(path) as db:
            db.row_factory=sqlite3.Row
            return [dict(r) for r in db.execute(f'SELECT * FROM "{table}" ORDER BY rowid DESC LIMIT ?',(limit,)).fetchall()]
    except Exception:return []

def paper_portfolio():
    candidates=[Path('data/baby_paper_trading.db'),Path('data/paper_trading.db')]
    p=next((x for x in candidates if x.exists()),candidates[0])
    tables=_sqlite_tables(p)
    payload={'status':'READY' if tables else 'NOT_AVAILABLE','database':str(p),'tables':tables,'real_money_execution':'DISABLED'}
    for t in tables:
        low=t.lower()
        if any(x in low for x in ('position','order','fill','trade','account','portfolio')):
            payload[t]=_rows(p,t,100)
    return payload

def automations():
    p=Path('data/baby_automations.db'); tables=_sqlite_tables(p)
    payload={'status':'READY' if tables else 'NOT_AVAILABLE','database':str(p),'tables':tables}
    for t in tables:
        if 'automation' in t.lower() or 'run' in t.lower(): payload[t]=_rows(p,t,100)
    return payload

def scanner():
    roots=[Path('data/market_scanner'),Path('data/scanner'),Path('data')]
    files=[]
    for root in roots:
        if root.exists(): files += [p for p in root.glob('*.json') if 'scan' in p.name.lower()]
    files=sorted(set(files),key=lambda p:p.stat().st_mtime,reverse=True)
    if not files:return {'status':'NOT_AVAILABLE','candidates':[]}
    p=files[0]; d=_read_json(p) or {}
    candidates=d.get('candidates') or d.get('results') or d.get('stocks') or []
    return {'status':'READY','source':str(p),'profile':d.get('profile'),'candidates':candidates[:100] if isinstance(candidates,list) else [],'raw_summary':{k:v for k,v in d.items() if k not in ('candidates','results','stocks')}}

def system_status():
    paths={'research':'data/ui_research','alerts':'data/baby_ui.db','automations':'data/baby_automations.db','paper':'data/baby_paper_trading.db','validation':'data/v7_5_real_investment_test.json'}
    return {'status':'ok','version':'8.2.0','time':datetime.now(timezone.utc).isoformat(),'ai_scoring_authority':0.0,'ai_execution_authority':0.0,'real_money_execution':'DISABLED','components':{k:{'path':v,'available':Path(v).exists()} for k,v in paths.items()}}
