from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, time
from zoneinfo import ZoneInfo
from math import isfinite

NY = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")

def _f(v, d=None):
    try:
        x=float(v)
        return x if isfinite(x) else d
    except Exception:
        return d

def _dt(v):
    if not v:
        return None
    s=str(v).strip().replace("Z","+00:00")
    try:
        d=datetime.fromisoformat(s)
    except Exception:
        return None
    if d.tzinfo is None:
        d=d.replace(tzinfo=UTC)
    return d.astimezone(NY)

@dataclass
class IntradayDataQuality:
    quality_state:str="UNKNOWN"
    trust_intraday_signals:bool=False
    trust_price_sequence:bool=False
    trust_volume_sequence:bool=False
    feed_scope:str="UNKNOWN"

    regular_session_bars:int=0
    expected_5m_bars:int=78
    coverage_ratio:float|None=None
    first_bar_et:str|None=None
    last_bar_et:str|None=None
    max_gap_minutes:float|None=None

    close_difference_pct:float|None=None
    high_difference_pct:float|None=None
    low_difference_pct:float|None=None
    volume_capture_ratio:float|None=None

    reasons:list[str]|None=None
    notes:list[str]|None=None

    def as_dict(self):
        return asdict(self)

def assess_intraday_quality(rows, daily_bar=None, expected_5m_bars=78, feed_scope="IEX"):
    rows=list(rows or [])
    daily_bar=daily_bar or {}
    feed_scope=str(feed_scope or "UNKNOWN").upper()
    reasons=[]
    notes=[]

    parsed=[]
    for r in rows:
        ts=_dt(r.get("timestamp") or r.get("datetime") or r.get("time"))
        if ts is None:
            continue
        if time(9,30) <= ts.time() < time(16,0):
            parsed.append((ts,r))
    parsed.sort(key=lambda x:x[0])

    n=len(parsed)
    coverage=n/expected_5m_bars if expected_5m_bars else None
    first=parsed[0][0] if parsed else None
    last=parsed[-1][0] if parsed else None

    max_gap=None
    if len(parsed)>=2:
        gaps=[(b[0]-a[0]).total_seconds()/60 for a,b in zip(parsed,parsed[1:])]
        max_gap=max(gaps) if gaps else None

    bars=[r for _,r in parsed]
    ih=max((_f(r.get("high"),float("-inf")) for r in bars),default=None)
    il=min((_f(r.get("low"),float("inf")) for r in bars),default=None)
    ic=_f(bars[-1].get("close")) if bars else None
    iv=sum((_f(r.get("volume"),0.0) or 0.0) for r in bars) if bars else None
    if ih==float("-inf"): ih=None
    if il==float("inf"): il=None

    dh=_f(daily_bar.get("high"))
    dl=_f(daily_bar.get("low"))
    dc=_f(daily_bar.get("close"))
    dv=_f(daily_bar.get("volume"))

    def pd(a,b):
        if a is None or b in (None,0):
            return None
        return abs(a-b)/abs(b)*100

    close_diff=pd(ic,dc)
    high_diff=pd(ih,dh)
    low_diff=pd(il,dl)
    vol_capture=(iv/dv) if iv is not None and dv not in (None,0) else None

    # PRICE-SEQUENCE trust is based on temporal continuity + OHLC reconciliation.
    price_trust=True
    if not parsed:
        price_trust=False
        reasons.append("No usable regular-session intraday bars.")
    if coverage is not None and coverage < 0.75:
        price_trust=False
        reasons.append(f"Only {n}/{expected_5m_bars} regular-session 5-minute bars were observed.")
    if max_gap is not None and max_gap > 15:
        price_trust=False
        reasons.append(f"Maximum regular-session gap is {max_gap:.0f} minutes.")
    if first is not None and first.time() > time(9,40):
        price_trust=False
        reasons.append(f"First regular-session bar is late ({first.strftime('%H:%M ET')}).")
    if last is not None and last.time() < time(15,45):
        price_trust=False
        reasons.append(f"Last regular-session bar is early ({last.strftime('%H:%M ET')}).")
    if close_diff is not None and close_diff > 1.0:
        price_trust=False
        reasons.append(f"Last intraday close differs from daily close by {close_diff:.2f}%.")
    if high_diff is not None and high_diff > 1.5:
        price_trust=False
        reasons.append(f"Intraday high differs from daily high by {high_diff:.2f}%.")
    if low_diff is not None and low_diff > 1.5:
        price_trust=False
        reasons.append(f"Intraday low differs from daily low by {low_diff:.2f}%.")

    # VOLUME trust is feed-aware.
    # IEX is only one venue, so comparing its volume to consolidated daily volume
    # is not a completeness test. Relative bar-volume patterns within IEX can still
    # be used when the time sequence itself is continuous.
    if feed_scope=="IEX":
        volume_trust=price_trust
        if vol_capture is not None:
            notes.append(
                f"IEX captured {vol_capture:.1%} of consolidated daily volume; "
                "this is expected for a single-venue feed and does not by itself invalidate the sequence."
            )
        notes.append(
            "IEX volume is suitable only for within-feed relative participation metrics, "
            "not for claims about total-market volume."
        )
    else:
        volume_trust=price_trust
        if vol_capture is not None and vol_capture < 0.75:
            volume_trust=False
            reasons.append(f"Feed captured only {vol_capture:.1%} of daily reported volume.")

    trust=price_trust and volume_trust

    if trust:
        state="TRUSTED"
    elif parsed and coverage is not None and coverage >= 0.50:
        state="LIMITED"
    elif parsed:
        state="UNTRUSTED"
    else:
        state="NO_DATA"

    return IntradayDataQuality(
        quality_state=state,
        trust_intraday_signals=trust,
        trust_price_sequence=price_trust,
        trust_volume_sequence=volume_trust,
        feed_scope=feed_scope,
        regular_session_bars=n,
        expected_5m_bars=expected_5m_bars,
        coverage_ratio=round(coverage,3) if coverage is not None else None,
        first_bar_et=first.isoformat() if first else None,
        last_bar_et=last.isoformat() if last else None,
        max_gap_minutes=round(max_gap,2) if max_gap is not None else None,
        close_difference_pct=round(close_diff,3) if close_diff is not None else None,
        high_difference_pct=round(high_diff,3) if high_diff is not None else None,
        low_difference_pct=round(low_diff,3) if low_diff is not None else None,
        volume_capture_ratio=round(vol_capture,4) if vol_capture is not None else None,
        reasons=reasons,
        notes=notes,
    )
