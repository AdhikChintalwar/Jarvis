from __future__ import annotations

from dataclasses import dataclass, asdict
from statistics import median
from math import isfinite


def _f(v, d=None):
    try:
        x = float(v)
        return x if isfinite(x) else d
    except Exception:
        return d


def _u(v):
    return str(v or "").strip().upper()


def _median(vals):
    vals = [_f(x) for x in vals]
    vals = [x for x in vals if x is not None]
    return median(vals) if vals else None


def _pct(a, b):
    a, b = _f(a), _f(b)
    if a is None or b in (None, 0):
        return None
    return (a / b - 1.0) * 100.0


def _atr(bars, n=14):
    if len(bars) < 2:
        return None
    trs = []
    prev = _f(bars[0].get("close"))
    for b in bars[1:]:
        h, l, c = _f(b.get("high")), _f(b.get("low")), _f(b.get("close"))
        if None not in (h, l, c, prev):
            trs.append(max(h - l, abs(h - prev), abs(l - prev)))
        if c is not None:
            prev = c
    if not trs:
        return None
    vals = trs[-n:]
    return sum(vals) / len(vals)


def _asset_type(symbol, candidate, report):
    for src in (candidate or {}, report or {}):
        v = _u(src.get("asset_type") or src.get("instrument_type") or src.get("security_type"))
        if v:
            if "ETF" in v or "FUND" in v:
                return "ETF"
            if "INDEX" in v:
                return "INDEX"
            if "EQUITY" in v or "STOCK" in v or "COMMON" in v:
                return "EQUITY"

    # Exact benchmark/common-market instruments only.
    # This is not a general ETF detector; live systems should pass metadata.
    if _u(symbol) in {"SPY","QQQ","IWM","DIA","VOO","VTI","XLF","XLK","XLE","TLT","GLD"}:
        return "ETF"
    return "EQUITY"


@dataclass
class RegimeAssessment:
    instrument_profile: str = "UNKNOWN"
    liquidity_profile: str = "UNKNOWN"
    volatility_profile: str = "UNKNOWN"
    behavior_regime: str = "UNKNOWN"
    research_state: str = "DISCOVERY"
    position_state: str = "NO_POSITION"
    flow_trend: str = "INSUFFICIENT_DATA"
    profile_confidence: str = "LOW"
    move_atr: float | None = None
    sma20_distance_atr: float | None = None
    volume_z_proxy: float | None = None
    rationale: list[str] | None = None
    contradictions: list[str] | None = None

    def as_dict(self):
        return asdict(self)


def _flow_trend(bars):
    if len(bars) < 8:
        return "INSUFFICIENT_DATA"

    vols = [_f(b.get("volume")) for b in bars]
    vols = [v for v in vols if v is not None and v > 0]
    if len(vols) < 8:
        return "INSUFFICIENT_DATA"

    recent = _median(vols[-3:])
    prior = _median(vols[-8:-3])
    if recent in (None, 0) or prior in (None, 0):
        return "INSUFFICIENT_DATA"

    ratio = recent / prior

    closes = [_f(b.get("close")) for b in bars]
    closes = [c for c in closes if c is not None]
    price_change = _pct(closes[-1], closes[-4]) if len(closes) >= 4 else None

    if ratio >= 1.35:
        return "FLOW_ACCELERATING"
    if ratio >= 0.85:
        return "FLOW_PERSISTENT"
    if price_change is not None and price_change > 2 and ratio < 0.65:
        return "FLOW_DIVERGENCE"
    if ratio < 0.65:
        return "FLOW_COOLING"
    return "FLOW_STABLE"


def assess(symbol, bars, base_intel, candidate=None, report=None, decision=None):
    candidate = candidate or {}
    report = report or {}
    decision = decision or {}
    bars = list(bars or [])

    if not bars:
        return RegimeAssessment()

    last = bars[-1]
    close = _f(last.get("close"))
    vol = _f(last.get("volume"))
    dollar_volume = close * vol if None not in (close, vol) else None

    a = _atr(bars)
    one_day = None
    if len(bars) >= 2:
        one_day = _pct(close, bars[-2].get("close"))

    move_atr = None
    if a not in (None, 0) and close is not None and len(bars) >= 2:
        prev_close = _f(bars[-2].get("close"))
        if prev_close is not None:
            move_atr = (close - prev_close) / a

    closes = [_f(b.get("close")) for b in bars]
    closes = [x for x in closes if x is not None]
    sma20 = sum(closes[-20:]) / 20 if len(closes) >= 20 else None
    sma20_dist_atr = None
    if a not in (None, 0) and close is not None and sma20 is not None:
        sma20_dist_atr = (close - sma20) / a

    ranges = []
    for b in bars[-20:]:
        h, l, c = _f(b.get("high")), _f(b.get("low")), _f(b.get("close"))
        if None not in (h, l, c) and c:
            ranges.append((h - l) / c * 100.0)
    typical_range = _median(ranges)

    vol_base = _median([_f(b.get("volume")) for b in bars[-21:-1]])
    volume_z_proxy = vol / vol_base if vol not in (None, 0) and vol_base not in (None, 0) else None

    asset = _asset_type(symbol, candidate, report)

    # Stable liquidity profile uses the recent median dollar volume, not today's
    # dollar volume. This prevents an instrument from changing identity because
    # of one unusually active or quiet session.
    recent_dollar_volumes=[]
    for b in bars[-20:]:
        cc,vv=_f(b.get("close")),_f(b.get("volume"))
        if None not in (cc,vv):
            recent_dollar_volumes.append(cc*vv)

    median_dollar_volume=_median(recent_dollar_volumes)

    if median_dollar_volume is None:
        liquidity = "UNKNOWN"
    elif median_dollar_volume >= 500_000_000:
        liquidity = "VERY_HIGH"
    elif median_dollar_volume >= 100_000_000:
        liquidity = "HIGH"
    elif median_dollar_volume >= 20_000_000:
        liquidity = "MEDIUM"
    else:
        liquidity = "LOW"

    if typical_range is None:
        vol_profile = "UNKNOWN"
    elif typical_range < 2.0:
        vol_profile = "LOW_VOLATILITY"
    elif typical_range < 4.5:
        vol_profile = "MODERATE_VOLATILITY"
    elif typical_range < 8.0:
        vol_profile = "HIGH_VOLATILITY"
    else:
        vol_profile = "EXTREME_VOLATILITY"

    # Do not infer market-cap class from price/volume behavior.
    if asset == "ETF":
        instrument = "ETF"
    elif vol_profile in {"HIGH_VOLATILITY","EXTREME_VOLATILITY"}:
        instrument = "HIGH_VOLATILITY_EQUITY"
    elif liquidity in {"VERY_HIGH","HIGH"}:
        instrument = "LIQUID_EQUITY"
    elif liquidity == "LOW":
        instrument = "LOW_LIQUIDITY_EQUITY"
    else:
        instrument = "GENERAL_EQUITY"

    if len(bars) >= 20:
        profile_confidence = "HIGH"
    elif len(bars) >= 10:
        profile_confidence = "MEDIUM"
    else:
        profile_confidence = "LOW"

    base_phase = _u(getattr(base_intel, "phase", "UNKNOWN"))
    base_stage = _u(getattr(base_intel, "stage", "DISCOVERY"))
    base_signal = _u(getattr(base_intel, "monitoring_signal", "CONTINUE"))
    base_flow = _u(getattr(getattr(base_intel, "flow", None), "label", "INSUFFICIENT_DATA"))

    flow_trend = _flow_trend(bars)

    # Behavior regime is descriptive and deliberately separate from trade state.
    if base_phase in {"FAILED_EXPANSION","CLIMACTIC_EXPANSION","POST_SPIKE_RESET"}:
        behavior = base_phase
    elif asset == "ETF" and base_phase in {"RESET","PULLBACK"}:
        behavior = "ETF_PULLBACK"
    elif base_phase == "EXPANSION" and flow_trend == "FLOW_ACCELERATING":
        behavior = "MOMENTUM_EXPANSION"
    elif base_phase == "EXPANSION":
        behavior = "EXPANSION"
    elif base_phase == "RE_ACCUMULATION":
        behavior = "RE_ACCUMULATION"
    elif base_phase == "CONSOLIDATION" and flow_trend in {"FLOW_ACCELERATING","FLOW_PERSISTENT"}:
        behavior = "CONSOLIDATION_WITH_FLOW"
    elif base_phase == "PULLBACK":
        behavior = "PULLBACK"
    elif base_phase == "RESET":
        behavior = "RESET"
    else:
        behavior = base_phase or "UNKNOWN"

    # Research state does NOT imply position management.
    if base_stage == "SETUP_READY":
        research_state = "SETUP_READY"
    elif base_stage == "SETUP_FORMING":
        research_state = "SETUP_FORMING"
    elif base_stage == "MONITOR":
        research_state = "MONITOR"
    elif base_stage == "RESEARCH":
        research_state = "RESEARCH"
    else:
        research_state = "DISCOVERY"

    reference_entry = None
    for src in (decision, report, candidate):
        reference_entry = _f((src or {}).get("reference_entry_price"))
        if reference_entry is not None:
            break

    if reference_entry is None:
        position_state = "NO_POSITION"
    elif base_signal in {"PROTECT_PROFIT","REVIEW","URGENT_REVIEW","DATA_ISSUE"}:
        position_state = base_signal
    else:
        position_state = "CONTINUE"

    rationale = [
        f"Instrument profile: {instrument}.",
        f"Liquidity profile: {liquidity}.",
        f"Volatility profile: {vol_profile}.",
        f"Behavior regime: {behavior}.",
        f"Flow trend: {flow_trend}.",
        f"Profile confidence: {profile_confidence}.",
    ]
    if median_dollar_volume is not None:
        rationale.append(f"Median recent dollar volume: ${median_dollar_volume:,.0f}.")
    if move_atr is not None:
        rationale.append(f"One-session move: {move_atr:+.2f} ATR.")
    if sma20_dist_atr is not None:
        rationale.append(f"Distance from SMA20: {sma20_dist_atr:+.2f} ATR.")
    if volume_z_proxy is not None:
        rationale.append(f"Volume relative to recent median: {volume_z_proxy:.2f}x.")

    contradictions = []
    if base_flow == "WEAK":
        contradictions.append("Base daily flow label is WEAK.")
    if flow_trend in {"FLOW_COOLING","FLOW_DIVERGENCE"}:
        contradictions.append(f"Participation trend is {flow_trend}.")
    if position_state == "NO_POSITION":
        contradictions.append("No monitored reference entry is present; position-risk alerts are not applicable.")

    return RegimeAssessment(
        instrument_profile=instrument,
        liquidity_profile=liquidity,
        volatility_profile=vol_profile,
        behavior_regime=behavior,
        research_state=research_state,
        position_state=position_state,
        flow_trend=flow_trend,
        profile_confidence=profile_confidence,
        move_atr=round(move_atr, 3) if move_atr is not None else None,
        sma20_distance_atr=round(sma20_dist_atr, 3) if sma20_dist_atr is not None else None,
        volume_z_proxy=round(volume_z_proxy, 3) if volume_z_proxy is not None else None,
        rationale=rationale,
        contradictions=contradictions,
    )
