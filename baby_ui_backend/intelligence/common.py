from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any
import math

def num(v):
    try:
        x=float(v); return x if math.isfinite(x) else None
    except (TypeError,ValueError): return None

def pct(a,b):
    a,b=num(a),num(b)
    return None if a is None or b in (None,0) else (a/b-1.0)*100.0

def safe_div(a,b):
    a,b=num(a),num(b); return None if a is None or b in (None,0) else a/b

def iso_now(): return datetime.now(timezone.utc).isoformat()

def status_for(value): return 'PASS' if value is not None else 'UNKNOWN'

@dataclass(frozen=True)
class Evidence:
    value: Any
    source: str
    authority: str
    as_of: str|None=None
    period: str|None=None
    form: str|None=None
    accession: str|None=None
    url: str|None=None
    verified: bool=False
    status: str='UNKNOWN'
    concept: str|None=None
    note: str|None=None
    def to_dict(self): return asdict(self)

def metric(key,label,value,*,unit=None,formula=None,inputs=None,evidence=None,interpretation='',status=None):
    return {'key':key,'label':label,'value':value,'unit':unit,'formula':formula,'inputs':inputs or {},
            'interpretation':interpretation,'status':status or status_for(value),
            'provenance':[e.to_dict() if hasattr(e,'to_dict') else e for e in (evidence or [])]}

def stage(id,label,metrics,*,summary='',status=None,score=None,warnings=None):
    known=sum(1 for m in metrics if m.get('value') is not None)
    coverage=round(100*known/max(1,len(metrics)),2)
    return {'id':id,'label':label,'status':status or ('PASS' if known else 'UNKNOWN'),'score':score,
            'coverage':coverage,'summary':summary,'metrics':metrics,'warnings':warnings or [],
            'generated_at':iso_now()}
