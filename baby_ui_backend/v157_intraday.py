from __future__ import annotations

from dataclasses import dataclass, asdict
from math import isfinite
from statistics import median


def _f(v, d=None):
    try:
        x=float(v)
        return x if isfinite(x) else d
    except Exception:
        return d


def _pct(a,b):
    a,b=_f(a),_f(b)
    if a is None or b in (None,0):
        return None
    return (a/b-1.0)*100.0


def _vwap(rows):
    num=0.0
    den=0.0
    for r in rows:
        h,l,c,v=_f(r.get("high")),_f(r.get("low")),_f(r.get("close")),_f(r.get("volume"))
        if None in (h,l,c,v) or v<=0:
            continue
        tp=(h+l+c)/3.0
        num += tp*v
        den += v
    return num/den if den else None


def _rolling_median(vals):
    vals=[_f(x) for x in vals]
    vals=[x for x in vals if x is not None]
    return median(vals) if vals else None


@dataclass
class IntradayAssessment:
    bars_seen:int=0

    session_vwap:float|None=None
    anchored_vwap:float|None=None
    price_vs_vwap_pct:float|None=None
    price_vs_anchored_vwap_pct:float|None=None

    opening_range_high:float|None=None
    opening_range_low:float|None=None
    opening_range_state:str="INSUFFICIENT_DATA"

    high_of_day:float|None=None
    high_of_day_rejection_pct:float|None=None
    lower_highs_count:int=0

    intraday_clv:float|None=None
    volume_acceleration:float|None=None
    intraday_rvol_proxy:float|None=None

    support_reclaim:bool=False
    support_loss:bool=False
    vwap_reclaim:bool=False
    vwap_loss:bool=False

    # Event semantics
    recent_breakout:bool=False
    failed_breakout_event:bool=False
    hod_rejection_event:bool=False
    breakdown_event:bool=False
    below_opening_range_support:bool=False
    breakdown_depth_or_width:float|None=None
    two_closes_below_opening_range:bool=False
    deterioration_confirmations:int=0

    intraday_regime:str="INSUFFICIENT_DATA"
    position_signal:str="NO_POSITION"

    reasons:list[str]|None=None
    contradictions:list[str]|None=None

    def as_dict(self):
        return asdict(self)


def assess_intraday(
    rows,
    reference_entry_price=None,
    anchor_index=0,
    opening_range_bars=3,
    prior_day_median_bar_volume=None,
    event_window_bars=6,
):
    """
    V15.7.6 intraday semantics.

    Key change:
    FAILED_INTRADAY_BREAKOUT and HIGH_OF_DAY_REJECTION are now RECENT EVENTS,
    not sticky all-day labels.

    event_window_bars defaults to 6 five-minute bars (~30 minutes).
    """
    rows=list(rows or [])
    if not rows:
        return IntradayAssessment()

    n=len(rows)
    last=rows[-1]
    close=_f(last.get("close"))
    high=max((_f(r.get("high"), float("-inf")) for r in rows), default=None)
    low=min((_f(r.get("low"), float("inf")) for r in rows), default=None)

    session_vwap=_vwap(rows)
    anchor_index=max(0,min(int(anchor_index or 0),n-1))
    anchored_vwap=_vwap(rows[anchor_index:])

    pvwap=_pct(close,session_vwap)
    pavwap=_pct(close,anchored_vwap)

    orb=rows[:max(1,min(opening_range_bars,n))]
    orh=max((_f(r.get("high"),float("-inf")) for r in orb),default=None)
    orl=min((_f(r.get("low"),float("inf")) for r in orb),default=None)

    if close is None or orh in (None,float("-inf")) or orl in (None,float("inf")):
        or_state="INSUFFICIENT_DATA"
    elif close>orh:
        or_state="ABOVE_OPENING_RANGE"
    elif close<orl:
        or_state="BELOW_OPENING_RANGE"
    else:
        or_state="INSIDE_OPENING_RANGE"

    hod_reject=None
    if close is not None and high not in (None,float("-inf"),0):
        hod_reject=(high-close)/high*100.0

    highs=[_f(r.get("high")) for r in rows[-5:]]
    highs=[x for x in highs if x is not None]
    lower_highs=0
    for a,b in zip(highs,highs[1:]):
        if b<a:
            lower_highs+=1

    if None not in (high,low,close) and high>low:
        session_clv=((close-low)-(high-close))/(high-low)
    else:
        session_clv=0.0

    vols=[_f(r.get("volume")) for r in rows]
    vols=[v for v in vols if v is not None and v>=0]

    volume_acc=None
    if len(vols)>=6:
        recent=_rolling_median(vols[-3:])
        prior=_rolling_median(vols[-6:-3])
        if recent is not None and prior not in (None,0):
            volume_acc=recent/prior

    intraday_rvol=None
    if prior_day_median_bar_volume not in (None,0) and vols:
        intraday_rvol=_rolling_median(vols[-3:])/float(prior_day_median_bar_volume)

    prev_close=_f(rows[-2].get("close")) if len(rows)>=2 else None
    prev_vwap=_vwap(rows[:-1]) if len(rows)>=2 else None

    vwap_reclaim=(
        prev_close is not None and prev_vwap not in (None,0) and
        prev_close<prev_vwap and close is not None and session_vwap is not None and
        close>session_vwap
    )
    vwap_loss=(
        prev_close is not None and prev_vwap not in (None,0) and
        prev_close>prev_vwap and close is not None and session_vwap is not None and
        close<session_vwap
    )

    support_reclaim=(
        orl not in (None,float("inf")) and prev_close is not None and close is not None and
        prev_close<orl and close>orl
    )
    support_loss=(
        orl not in (None,float("inf")) and prev_close is not None and close is not None and
        prev_close>orl and close<orl
    )

    # ------------------------------------------------------------------
    # EVENT SEMANTICS
    # ------------------------------------------------------------------
    recent_start=max(opening_range_bars, n-max(1,event_window_bars))
    recent_rows=rows[recent_start:]

    recent_breakout=False
    if orh not in (None,float("-inf")):
        recent_breakout=any(
            _f(r.get("high"),float("-inf"))>orh
            for r in recent_rows
        )

    # Find when the session HOD happened. A rejection is "current" only if the
    # HOD itself happened recently.
    hod_index=None
    if high not in (None,float("-inf")):
        for i in range(len(rows)-1,-1,-1):
            if _f(rows[i].get("high")) == high:
                hod_index=i
                break
    hod_is_recent = hod_index is not None and (n-1-hod_index) < max(1,event_window_bars)

    failed_breakout_event=bool(
        recent_breakout and
        close is not None and orh not in (None,float("-inf")) and
        close<orh and
        hod_reject is not None and hod_reject>=1.0
    )

    hod_rejection_event=bool(
        hod_is_recent and
        hod_reject is not None and hod_reject>=2.0 and
        session_clv<=-0.35
    )

    # Breakdown confirmation is an EVENT, not a permanent state.
    #
    # V15.7.7 correctly required persistence/depth, but once two closes were
    # below ORL, every later bar below ORL also satisfied the condition.
    # That made INTRADAY_BREAKDOWN sticky for the rest of the session.
    #
    # V15.7.8 detects the actual confirmation moment and lets that event decay.
    opening_range_width=None
    if orh not in (None,float("-inf")) and orl not in (None,float("inf")):
        opening_range_width=orh-orl

    breakdown_depth=None
    if close is not None and orl not in (None,float("inf")) and opening_range_width not in (None,0):
        breakdown_depth=(orl-close)/opening_range_width

    recent_breakdown_trigger=False
    two_closes_below_orl=False
    decisive_break=False

    # Keep breakdown event shorter than general breakout/rejection events.
    breakdown_window_bars=min(max(1,event_window_bars),3)
    trigger_start=max(opening_range_bars, n-breakdown_window_bars)

    closes=[_f(r.get("close")) for r in rows]

    for j in range(trigger_start, n):
        cj=closes[j]
        if cj is None or orl in (None,float("inf")):
            continue

        prev=closes[j-1] if j>=1 else None
        prev2=closes[j-2] if j>=2 else None

        # Persistence trigger occurs exactly when the SECOND consecutive
        # below-support close appears after previously being at/above support.
        persistent_trigger=bool(
            j>=2 and
            cj<orl and
            prev is not None and prev<orl and
            prev2 is not None and prev2>=orl
        )

        # Decisive trigger occurs on a fresh break from at/above support.
        depth_j=None
        if opening_range_width not in (None,0):
            depth_j=(orl-cj)/opening_range_width

        decisive_trigger=bool(
            cj<orl and
            prev is not None and prev>=orl and
            depth_j is not None and depth_j>=0.20
        )

        if persistent_trigger:
            two_closes_below_orl=True
            recent_breakdown_trigger=True

        if decisive_trigger:
            decisive_break=True
            recent_breakdown_trigger=True

    breakdown_event=bool(
        recent_breakdown_trigger and
        close is not None and session_vwap is not None and
        close<session_vwap and
        orl not in (None,float("inf")) and
        close<orl
    )

    confirmations=0
    if close is not None and session_vwap is not None and close<session_vwap:
        confirmations += 1
    if lower_highs>=2:
        confirmations += 1
    if session_clv<=-0.35:
        confirmations += 1
    if failed_breakout_event:
        confirmations += 1
    if hod_rejection_event:
        confirmations += 1
    if support_loss:
        confirmations += 1

    # Snapshot regime. Event labels can only remain while their RECENT event
    # conditions are still true.
    if breakdown_event and confirmations>=3:
        regime="INTRADAY_BREAKDOWN"
    elif failed_breakout_event and confirmations>=3:
        regime="FAILED_INTRADAY_BREAKOUT"
    elif hod_rejection_event and confirmations>=3:
        regime="HIGH_OF_DAY_REJECTION"
    elif vwap_reclaim and or_state=="ABOVE_OPENING_RANGE":
        regime="VWAP_RECLAIM_BREAKOUT"
    elif or_state=="ABOVE_OPENING_RANGE" and session_vwap is not None and close is not None and close>session_vwap:
        regime="OPENING_RANGE_BREAKOUT"
    elif close is not None and session_vwap is not None and close>session_vwap:
        regime="ABOVE_VWAP"
    elif close is not None and session_vwap is not None and close<session_vwap:
        regime="BELOW_VWAP"
    else:
        regime="BALANCED"

    # Position state needs stronger confluence than descriptive regime state.
    if reference_entry_price in (None,0):
        position_signal="NO_POSITION"
    else:
        gain=_pct(close,reference_entry_price)

        severe_breakdown = breakdown_event and confirmations>=4
        confirmed_failure = failed_breakout_event and confirmations>=4
        confirmed_rejection = hod_rejection_event and confirmations>=4

        if severe_breakdown and gain is not None and gain<0:
            position_signal="URGENT_REVIEW"
        elif confirmed_failure:
            position_signal="PROTECT_PROFIT" if gain is not None and gain>0 else "REVIEW"
        elif confirmed_rejection and gain is not None and gain>=5:
            position_signal="PROTECT_PROFIT"
        else:
            position_signal="CONTINUE"

    reasons=[
        f"Intraday regime: {regime}.",
        f"Opening-range state: {or_state}.",
        f"Deterioration confirmations: {confirmations}.",
    ]
    if session_vwap is not None:
        reasons.append(f"Session VWAP: {session_vwap:.4f}.")
    if pvwap is not None:
        reasons.append(f"Price versus VWAP: {pvwap:+.2f}%.")
    if hod_reject is not None:
        reasons.append(f"High-of-day rejection: {hod_reject:.2f}%.")
    if failed_breakout_event:
        reasons.append("Recent breakout has failed back below the opening-range high.")
    if hod_rejection_event:
        reasons.append("Recent session high is being rejected.")
    if breakdown_event:
        if two_closes_below_orl:
            reasons.append("Opening-range support is confirmed lost by two consecutive closes below it while below VWAP.")
        elif decisive_break:
            reasons.append("Opening-range support was decisively broken below VWAP.")
    if volume_acc is not None:
        reasons.append(f"Recent within-feed volume acceleration ratio: {volume_acc:.2f}x.")
    if lower_highs:
        reasons.append(f"Lower-high transitions in recent bars: {lower_highs}.")

    contradictions=[]
    if regime in {"OPENING_RANGE_BREAKOUT","VWAP_RECLAIM_BREAKOUT","ABOVE_VWAP"} and volume_acc is not None and volume_acc<0.7:
        contradictions.append("Price strength is occurring while recent within-feed bar volume is cooling.")
    if regime in {"FAILED_INTRADAY_BREAKOUT","HIGH_OF_DAY_REJECTION"} and volume_acc is not None and volume_acc>1.3:
        contradictions.append("Deterioration is occurring with accelerating within-feed participation.")
    if position_signal=="NO_POSITION":
        contradictions.append("No reference entry supplied; position-risk state is not applicable.")

    return IntradayAssessment(
        bars_seen=n,
        session_vwap=round(session_vwap,6) if session_vwap is not None else None,
        anchored_vwap=round(anchored_vwap,6) if anchored_vwap is not None else None,
        price_vs_vwap_pct=round(pvwap,3) if pvwap is not None else None,
        price_vs_anchored_vwap_pct=round(pavwap,3) if pavwap is not None else None,
        opening_range_high=round(orh,6) if orh not in (None,float("-inf")) else None,
        opening_range_low=round(orl,6) if orl not in (None,float("inf")) else None,
        opening_range_state=or_state,
        high_of_day=round(high,6) if high not in (None,float("-inf")) else None,
        high_of_day_rejection_pct=round(hod_reject,3) if hod_reject is not None else None,
        lower_highs_count=lower_highs,
        intraday_clv=round(session_clv,3),
        volume_acceleration=round(volume_acc,3) if volume_acc is not None else None,
        intraday_rvol_proxy=round(intraday_rvol,3) if intraday_rvol is not None else None,
        support_reclaim=support_reclaim,
        support_loss=support_loss,
        vwap_reclaim=vwap_reclaim,
        vwap_loss=vwap_loss,
        recent_breakout=recent_breakout,
        failed_breakout_event=failed_breakout_event,
        hod_rejection_event=hod_rejection_event,
        breakdown_event=breakdown_event,
        below_opening_range_support=bool(
            close is not None and
            orl not in (None,float("inf")) and
            close<orl
        ),
        breakdown_depth_or_width=round(breakdown_depth,3) if breakdown_depth is not None else None,
        two_closes_below_opening_range=two_closes_below_orl,
        deterioration_confirmations=confirmations,
        intraday_regime=regime,
        position_signal=position_signal,
        reasons=reasons,
        contradictions=contradictions,
    )
