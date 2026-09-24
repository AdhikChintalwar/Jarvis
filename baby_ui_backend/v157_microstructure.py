from __future__ import annotations
from dataclasses import dataclass,asdict
from math import isfinite

def _f(v,d=None):
    try:
        x=float(v)
        return x if isfinite(x) else d
    except Exception:
        return d

@dataclass
class MicrostructureSnapshot:
    spread_pct:float|None=None
    quote_imbalance:float|None=None
    last_trade_location:str="UNKNOWN"
    aggression_estimate:str="UNKNOWN"
    quality_state:str="INSUFFICIENT_DATA"
    notes:list[str]|None=None
    def as_dict(self):return asdict(self)

def assess_quote(bid=None,ask=None,bid_size=None,ask_size=None,last_price=None):
    bid,ask,bid_size,ask_size,last_price=map(_f,(bid,ask,bid_size,ask_size,last_price))
    notes=[]
    if bid is None or ask is None or ask<=bid:
        return MicrostructureSnapshot(notes=["Valid bid/ask pair is required."])

    mid=(bid+ask)/2
    spread=(ask-bid)/mid*100 if mid else None

    imb=None
    if bid_size is not None and ask_size is not None and (bid_size+ask_size)>0:
        imb=(bid_size-ask_size)/(bid_size+ask_size)

    loc="UNKNOWN"
    aggr="UNKNOWN"
    if last_price is not None:
        if last_price>=ask:
            loc="AT_OR_ABOVE_ASK";aggr="BUY_SIDE_AGGRESSION_ESTIMATE"
        elif last_price<=bid:
            loc="AT_OR_BELOW_BID";aggr="SELL_SIDE_AGGRESSION_ESTIMATE"
        elif last_price>mid:
            loc="ABOVE_MID";aggr="MILD_BUY_SIDE_ESTIMATE"
        elif last_price<mid:
            loc="BELOW_MID";aggr="MILD_SELL_SIDE_ESTIMATE"
        else:
            loc="AT_MID";aggr="BALANCED"

    quality="GOOD"
    if spread is not None and spread>2:
        quality="POOR_SPREAD"
    elif spread is not None and spread>1:
        quality="WIDE_SPREAD"

    notes.append("Aggression is an estimate from quote/trade location, not proof of buyer/seller identity.")
    notes.append("Do not infer institutional activity from this snapshot alone.")

    return MicrostructureSnapshot(
        spread_pct=round(spread,4) if spread is not None else None,
        quote_imbalance=round(imb,4) if imb is not None else None,
        last_trade_location=loc,
        aggression_estimate=aggr,
        quality_state=quality,
        notes=notes,
    )
