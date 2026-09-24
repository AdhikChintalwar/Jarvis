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


def _sma(vals,n):
    vals=[_f(x) for x in vals]
    vals=[x for x in vals if x is not None]
    if len(vals)<n:
        return None
    return sum(vals[-n:])/n


def _ret(rows,n):
    if len(rows)<n+1:
        return None
    a=_f(rows[-1].get("close"))
    b=_f(rows[-(n+1)].get("close"))
    return _pct(a,b)


def _trend(rows):
    if not rows:
        return "UNKNOWN"
    closes=[_f(x.get("close")) for x in rows]
    closes=[x for x in closes if x is not None]
    if len(closes)<20:
        return "INSUFFICIENT_DATA"

    c=closes[-1]
    s5=_sma(closes,5)
    s20=_sma(closes,20)
    if None in (c,s5,s20):
        return "INSUFFICIENT_DATA"

    if c>s5>s20:
        return "UPTREND"
    if c<s5<s20:
        return "DOWNTREND"
    if c>s20:
        return "ABOVE_TREND"
    if c<s20:
        return "BELOW_TREND"
    return "MIXED"


@dataclass
class MarketContext:
    market_regime:str="UNKNOWN"
    broad_market_trend:str="UNKNOWN"
    smallcap_trend:str="UNKNOWN"
    sector_trend:str="UNKNOWN"
    volatility_regime:str="UNKNOWN"

    stock_return_5d:float|None=None
    market_return_5d:float|None=None
    relative_strength_5d:float|None=None

    stock_return_20d:float|None=None
    market_return_20d:float|None=None
    relative_strength_20d:float|None=None

    breadth_proxy:str="UNKNOWN"
    context_signal:str="NEUTRAL"
    rationale:list[str]|None=None
    contradictions:list[str]|None=None

    def as_dict(self):
        return asdict(self)


def assess_market_context(
    stock_rows,
    market_rows=None,
    smallcap_rows=None,
    sector_rows=None,
    vix_rows=None,
):
    stock_rows=list(stock_rows or [])
    market_rows=list(market_rows or [])
    smallcap_rows=list(smallcap_rows or [])
    sector_rows=list(sector_rows or [])
    vix_rows=list(vix_rows or [])

    broad=_trend(market_rows)
    small=_trend(smallcap_rows)
    sector=_trend(sector_rows)

    s5=_ret(stock_rows,5)
    m5=_ret(market_rows,5)
    rs5=(s5-m5) if None not in (s5,m5) else None

    s20=_ret(stock_rows,20)
    m20=_ret(market_rows,20)
    rs20=(s20-m20) if None not in (s20,m20) else None

    vix_regime="UNKNOWN"
    if vix_rows:
        vc=_f(vix_rows[-1].get("close"))
        vbase=_sma([x.get("close") for x in vix_rows],20)
        if vc is not None:
            if vc>=30:
                vix_regime="VERY_HIGH_VOLATILITY"
            elif vc>=22:
                vix_regime="HIGH_VOLATILITY"
            elif vc<=15:
                vix_regime="LOW_VOLATILITY"
            else:
                vix_regime="NORMAL_VOLATILITY"
            if vbase not in (None,0):
                if vc>=1.25*vbase:
                    vix_regime="VOLATILITY_SPIKE"
                elif vc<=0.80*vbase:
                    vix_regime="VOLATILITY_COMPRESSION"

    # Simple breadth proxy from SPY/IWM trend agreement.
    if broad=="UPTREND" and small=="UPTREND":
        breadth="BROAD_RISK_ON"
    elif broad=="DOWNTREND" and small=="DOWNTREND":
        breadth="BROAD_RISK_OFF"
    elif broad=="UPTREND" and small in {"DOWNTREND","BELOW_TREND"}:
        breadth="NARROW_LARGE_CAP_LEADERSHIP"
    elif broad in {"DOWNTREND","BELOW_TREND"} and small=="UPTREND":
        breadth="SMALLCAP_DIVERGENCE"
    else:
        breadth="MIXED"

    # Market regime is descriptive, not predictive.
    if vix_regime in {"VOLATILITY_SPIKE","VERY_HIGH_VOLATILITY"}:
        regime="STRESS"
    elif broad=="UPTREND" and small=="UPTREND":
        regime="RISK_ON"
    elif broad=="DOWNTREND" and small=="DOWNTREND":
        regime="RISK_OFF"
    elif broad=="UPTREND":
        regime="SELECTIVE_RISK_ON"
    elif broad=="DOWNTREND":
        regime="SELECTIVE_RISK_OFF"
    else:
        regime="MIXED"

    # Context signal answers: is the external environment helping or opposing?
    supportive=0
    opposing=0

    if broad in {"UPTREND","ABOVE_TREND"}: supportive+=1
    if broad in {"DOWNTREND","BELOW_TREND"}: opposing+=1

    if sector in {"UPTREND","ABOVE_TREND"}: supportive+=1
    if sector in {"DOWNTREND","BELOW_TREND"}: opposing+=1

    if rs20 is not None:
        if rs20>=5: supportive+=1
        elif rs20<=-5: opposing+=1

    if vix_regime in {"VOLATILITY_SPIKE","VERY_HIGH_VOLATILITY","HIGH_VOLATILITY"}:
        opposing+=1

    if supportive>=2 and opposing==0:
        context_signal="SUPPORTIVE"
    elif opposing>=2 and supportive==0:
        context_signal="ADVERSE"
    elif supportive>opposing:
        context_signal="MILDLY_SUPPORTIVE"
    elif opposing>supportive:
        context_signal="MILDLY_ADVERSE"
    else:
        context_signal="NEUTRAL"

    rationale=[
        f"Broad-market trend: {broad}.",
        f"Small-cap trend: {small}.",
        f"Sector trend: {sector}.",
        f"Volatility regime: {vix_regime}.",
        f"Breadth proxy: {breadth}.",
        f"External context: {context_signal}.",
    ]
    if rs5 is not None:
        rationale.append(f"5-day stock minus market relative strength: {rs5:+.2f} percentage points.")
    if rs20 is not None:
        rationale.append(f"20-day stock minus market relative strength: {rs20:+.2f} percentage points.")

    contradictions=[]
    if broad in {"DOWNTREND","BELOW_TREND"} and rs20 is not None and rs20>5:
        contradictions.append("Stock is outperforming despite weak broad-market context.")
    if broad in {"UPTREND","ABOVE_TREND"} and rs20 is not None and rs20<-5:
        contradictions.append("Stock is underperforming despite supportive broad-market context.")
    if sector in {"DOWNTREND","BELOW_TREND"} and rs20 is not None and rs20>5:
        contradictions.append("Stock strength conflicts with weak sector context.")
    if vix_regime in {"VOLATILITY_SPIKE","VERY_HIGH_VOLATILITY"}:
        contradictions.append("Market volatility is elevated; breakout/follow-through reliability may be lower.")

    return MarketContext(
        market_regime=regime,
        broad_market_trend=broad,
        smallcap_trend=small,
        sector_trend=sector,
        volatility_regime=vix_regime,
        stock_return_5d=round(s5,3) if s5 is not None else None,
        market_return_5d=round(m5,3) if m5 is not None else None,
        relative_strength_5d=round(rs5,3) if rs5 is not None else None,
        stock_return_20d=round(s20,3) if s20 is not None else None,
        market_return_20d=round(m20,3) if m20 is not None else None,
        relative_strength_20d=round(rs20,3) if rs20 is not None else None,
        breadth_proxy=breadth,
        context_signal=context_signal,
        rationale=rationale,
        contradictions=contradictions,
    )
