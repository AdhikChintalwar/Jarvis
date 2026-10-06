from __future__ import annotations

import os


def _f(v):
    try:return float(v)
    except Exception:return None

def _b(v):
    return v is True or str(v or '').strip().upper() in {'1','TRUE','YES','Y'}

def _symbol(x):return str(x.get('symbol') or x.get('ticker') or '').upper().strip()

def lane(x):
    fs=_f(x.get('flow_score')) or 0
    rv=_f(x.get('relative_volume') or x.get('rvol')) or 0
    cl=_f(x.get('close_location_pct'))
    if cl is None:
        clv=_f(x.get('close_location')); cl=(clv*100 if clv is not None and clv<=1 else clv)
    dv=_f(x.get('current_dollar_volume') or x.get('dollar_volume')) or 0
    ch=_f(x.get('daily_change_pct') or x.get('change_pct') or x.get('return_1d_pct')) or 0
    r5=_f(x.get('return_5d_pct'))
    r20=_f(x.get('return_20d_pct'))
    hv=_f(x.get('high_volume_days_5d')) or 0
    ft=str(x.get('flow_type') or '').upper()
    if _b(x.get('breakout_20d')) and fs>=70 and rv>=1.25:return 'BREAKOUT'
    if fs>=85 or ft in {'STRONG_ACCUMULATION','BULLISH_FLOW'}:return 'FLOW_MOMENTUM'
    if r20 is not None and r20>=5 and r5 is not None and -6<=r5<=4 and rv>=1.15:return 'REACCUMULATION'
    if fs>=68 and rv>=1.25 and (cl or 0)>=65:return 'TECHNICAL_RECOVERY'
    if abs(ch)>=8 and rv>=2 and dv>=5_000_000:return 'HIGH_VOL_EVENT_RESEARCH'
    if hv>=2 and rv>=1.3 and fs>=70:return 'PERSISTENT_FLOW'
    return None


def select_candidates(rows,base_limit=5):
    """Diversified research discovery only. Does not alter PAPER eligibility."""
    max_total=max(int(base_limit),min(int(os.getenv('BABY_V1511_DISCOVERY_MAX','12')),20))
    selected=[];seen=set()
    def add(x):
        s=_symbol(x)
        if s and s not in seen and len(selected)<max_total:
            y=dict(x);y['v1511_discovery_lane']=lane(x) or 'BASELINE';selected.append(y);seen.add(s)
    for x in list(rows)[:int(base_limit)]:add(x)
    ranked=[]
    for x in rows:
        l=lane(x)
        if not l:continue
        fs=_f(x.get('flow_score')) or 0;rv=_f(x.get('relative_volume') or x.get('rvol')) or 0;dv=_f(x.get('current_dollar_volume') or x.get('dollar_volume')) or 0
        bonus={'BREAKOUT':10,'FLOW_MOMENTUM':9,'REACCUMULATION':8,'TECHNICAL_RECOVERY':7,'HIGH_VOL_EVENT_RESEARCH':6,'PERSISTENT_FLOW':5}.get(l,0)
        ranked.append((bonus+fs/20+min(rv,5)+min(dv/10_000_000,3),x))
    for _,x in sorted(ranked,key=lambda z:z[0],reverse=True):add(x)
    return selected
