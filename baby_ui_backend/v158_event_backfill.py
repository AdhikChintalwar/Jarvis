from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from types import SimpleNamespace
import csv

from baby_ui_backend.v156_event_risk import assess_events
from baby_ui_backend.v157_fusion import fuse


CANONICAL_EVENT_FIELDS = {
    "symbol",
    "published_at",
    "headline",
    "source",
    "url",
    "form",
    "event_type",
    "source_tier",
}


def _dt(v):
    if v is None or str(v).strip()=="":
        return None
    s=str(v).strip().replace("Z","+00:00")
    d=datetime.fromisoformat(s)
    if d.tzinfo is None:
        d=d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc)


def _as_dict(x):
    if x is None:
        return {}
    if isinstance(x,dict):
        return dict(x)
    if is_dataclass(x):
        return asdict(x)
    if hasattr(x,"as_dict"):
        return x.as_dict()
    if hasattr(x,"__dict__"):
        return dict(vars(x))
    return {}


def load_events_csv(path):
    out=[]
    with open(path,newline="") as f:
        for r in csv.DictReader(f):
            x={str(k).strip():v for k,v in r.items()}
            if not str(x.get("headline") or "").strip():
                continue
            # Normalize common aliases without deleting the originals.
            if not x.get("published_at"):
                x["published_at"]=x.get("timestamp") or x.get("created_at") or x.get("date")
            if not x.get("source"):
                x["source"]=x.get("domain") or x.get("provider")
            if not x.get("url"):
                x["url"]=x.get("link")
            out.append(x)
    return out


def point_in_time_events(rows, symbol, as_of):
    """
    Return only events that were knowable by as_of.

    Date-only as_of is treated as end-of-day UTC for historical daily replay.
    This is conservative for daily replay but is NOT minute-perfect intraday replay.
    """
    sym=str(symbol or "").upper().strip()
    raw_as_of=str(as_of or "").strip()

    if len(raw_as_of)==10:
        cutoff=_dt(raw_as_of+"T23:59:59+00:00")
    else:
        cutoff=_dt(raw_as_of)

    if cutoff is None:
        raise ValueError("as_of is required and must be ISO date/datetime")

    seen=set()
    out=[]
    for r in rows or []:
        rsym=str(r.get("symbol") or sym).upper().strip()
        if rsym and rsym!=sym:
            continue

        pub=_dt(
            r.get("published_at")
            or r.get("timestamp")
            or r.get("created_at")
            or r.get("date")
        )
        if pub is None or pub>cutoff:
            continue

        headline=str(r.get("headline") or r.get("title") or "").strip()
        if not headline:
            continue

        key=(headline.lower(),pub.isoformat(),str(r.get("source") or "").lower())
        if key in seen:
            continue
        seen.add(key)

        x=dict(r)
        x["symbol"]=sym
        x["published_at"]=pub.isoformat().replace("+00:00","Z")
        out.append(x)

    out.sort(key=lambda x:_dt(x["published_at"]))
    return out


def _probe_assess(symbol, events, as_of):
    """
    Current Baby event engine has evolved across versions. This adapter discovers
    which supported evidence container the installed v156_event_risk uses, instead
    of hard-coding an obsolete internal path.
    """
    attempts=[
        ("report.news", {}, {"news":events}, {}),
        ("report.recent_news", {}, {"recent_news":events}, {}),
        ("report.events", {}, {"events":events}, {}),
        ("candidate.news", {"news":events}, {}, {}),
        ("candidate.events", {"events":events}, {}, {}),
        ("decision.research_decision.news", {}, {}, {"research_decision":{"news":events}}),
        ("decision.proposal.payload.news", {}, {}, {"proposal":{"payload":{"news":events}}}),
        ("decision.proposal.payload.events", {}, {}, {"proposal":{"payload":{"events":events}}}),
    ]

    last=None
    for label,candidate,report,decision in attempts:
        try:
            a=assess_events(
                symbol,
                candidate=candidate,
                report=report,
                decision=decision,
                as_of=as_of,
            )
            last=a
            seen=getattr(a,"events_seen",None)
            if events and isinstance(seen,int) and seen>0:
                return a,label
            if not events:
                return a,label
        except Exception:
            continue

    if last is not None:
        return last,"UNKNOWN_CONTAINER"
    raise RuntimeError("Installed assess_events could not be called with supported evidence containers.")


def assess_event_backfill(symbol, rows, as_of):
    visible=point_in_time_events(rows,symbol,as_of)
    assessment,container=_probe_assess(symbol,visible,as_of)
    return {
        "symbol":str(symbol).upper(),
        "as_of":str(as_of),
        "visible_event_count":len(visible),
        "visible_events":visible,
        "engine_container":container,
        "assessment":assessment,
    }


def _ns(x):
    if x is None:
        return None
    if isinstance(x,SimpleNamespace):
        return x
    if isinstance(x,dict):
        return SimpleNamespace(**x)
    return x


def normalize_intraday_for_fusion(intraday):
    """
    Production-safe bridge:
    if replay/data-quality produced an effective signal, that signal has authority
    over a raw intraday position signal.
    """
    if intraday is None:
        return None

    d=_as_dict(intraday)
    if not d:
        return intraday

    effective=d.get("effective_position_signal")
    trusted=d.get("trust_intraday_signals")

    if effective:
        d["position_signal"]=effective
    elif trusted is False:
        d["position_signal"]="DATA_ISSUE"

    return SimpleNamespace(**d)


def _get(obj,name,default=None):
    if obj is None:
        return default
    if isinstance(obj,dict):
        return obj.get(name,default)
    return getattr(obj,name,default)


def _append_unique(dst,msg):
    if msg and msg not in dst:
        dst.append(msg)


def _enrich_contradictions(snapshot,regime,event_risk,market_context,intraday):
    if snapshot is None:
        return snapshot

    existing=list(_get(snapshot,"contradictions",[]) or [])

    event_overlay=str(_get(snapshot,"event_overlay","NONE") or "NONE").upper()
    risk_overlay=str(_get(snapshot,"risk_overlay","NORMAL") or "NORMAL").upper()
    context_overlay=str(_get(snapshot,"context_overlay","NEUTRAL") or "NEUTRAL").upper()
    final_position=str(_get(snapshot,"final_position_state","NO_POSITION") or "NO_POSITION").upper()

    flow_trend=str(_get(regime,"flow_trend","") or "").upper()
    behavior=str(_get(regime,"behavior_regime","") or "").upper()
    intraday_regime=str(_get(intraday,"intraday_regime","") or "").upper()
    raw_signal=str(_get(intraday,"raw_position_signal",_get(intraday,"position_signal","")) or "").upper()
    effective_signal=str(_get(intraday,"effective_position_signal","") or "").upper()
    trusted=_get(intraday,"trust_intraday_signals",None)

    structural_level=str(_get(event_risk,"structural_risk_level","LOW") or "LOW").upper()
    causality=str(_get(event_risk,"catalyst_causality","NOT_ESTABLISHED") or "NOT_ESTABLISHED").upper()

    strong_price = (
        behavior in {"FLOW_PERSISTENT","BREAKOUT","CONSOLIDATION_WITH_FLOW"}
        or flow_trend in {"FLOW_PERSISTENT","FLOW_ACCELERATING"}
        or intraday_regime in {"OPENING_RANGE_BREAKOUT","VWAP_RECLAIM_BREAKOUT","ABOVE_VWAP"}
    )

    adverse_context = context_overlay in {"ADVERSE","RISK_OFF"}
    structural_risk_active = (
        structural_level in {"MODERATE","HIGH","CRITICAL"}
        or "MODERATE" in risk_overlay
        or "HIGH" in risk_overlay
        or "CRITICAL" in risk_overlay
    )

    if adverse_context and strong_price:
        _append_unique(existing,
            "Stock-specific price/flow strength conflicts with adverse broader-market context.")

    if event_overlay=="EVENT_DRIVEN_FINANCING" and strong_price and structural_risk_active:
        _append_unique(existing,
            "Strong price/flow evidence coexists with financing-related structural risk; the catalyst does not cancel capital-structure risk.")

    if event_overlay not in {"NONE","UNKNOWN",""} and causality=="NOT_ESTABLISHED":
        _append_unique(existing,
            "A company-specific event is present, but Baby does not establish that the event caused the observed price move.")

    if trusted is False or effective_signal=="DATA_ISSUE" or final_position=="DATA_ISSUE":
        if raw_signal and raw_signal not in {"","NO_POSITION","CONTINUE","DATA_ISSUE"}:
            _append_unique(existing,
                f"Raw intraday signal {raw_signal} is not trusted because intraday data quality is insufficient; DATA_ISSUE has authority.")
        else:
            _append_unique(existing,
                "Intraday evidence is not trusted because data quality is insufficient.")

    if final_position=="PROTECT_PROFIT" and adverse_context:
        _append_unique(existing,
            "Trusted intraday deterioration is reinforced by adverse market context.")

    for src in (regime,event_risk,market_context,intraday):
        for msg in (_get(src,"contradictions",[]) or []):
            _append_unique(existing,str(msg))

    try:
        snapshot.contradictions=existing
        return snapshot
    except Exception:
        pass

    if isinstance(snapshot,dict):
        snapshot=dict(snapshot)
        snapshot["contradictions"]=existing
        return snapshot

    return snapshot


def fuse_point_in_time(regime=None,event_risk=None,market_context=None,intraday=None):
    safe_intraday=normalize_intraday_for_fusion(intraday)
    snapshot=fuse(
        regime=_ns(regime),
        event_risk=_ns(event_risk),
        market_context=_ns(market_context),
        intraday=safe_intraday,
    )
    return _enrich_contradictions(
        snapshot,
        regime=_ns(regime),
        event_risk=_ns(event_risk),
        market_context=_ns(market_context),
        intraday=safe_intraday,
    )
