#!/usr/bin/env python3
from pathlib import Path
from types import SimpleNamespace
import argparse, json, sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

from baby_ui_backend.v158_event_backfill import (
    load_events_csv,
    assess_event_backfill,
    fuse_point_in_time,
)

EVENTS_DEFAULT=ROOT/"examples/v158_synthetic_events.csv"


def regime(research="MONITOR", position="NO_POSITION",
           behavior="FLOW_PERSISTENT", flow="FLOW_PERSISTENT"):
    return SimpleNamespace(
        research_state=research,
        position_state=position,
        behavior_regime=behavior,
        instrument_profile="LIQUID_EQUITY",
        flow_trend=flow,
        contradictions=[],
        rationale=[
            f"Research state: {research}.",
            f"Behavior regime: {behavior}.",
            f"Flow trend: {flow}.",
        ],
    )


def market(signal="NEUTRAL", regime_name="MIXED", contradictions=None):
    return SimpleNamespace(
        context_signal=signal,
        market_regime=regime_name,
        broad_market_trend="UNKNOWN",
        smallcap_trend="UNKNOWN",
        sector_trend="UNKNOWN",
        volatility_regime="UNKNOWN",
        contradictions=list(contradictions or []),
        rationale=[f"Market context signal: {signal}."],
    )


def intraday(regime_name="ABOVE_VWAP", position="CONTINUE",
             effective=None, trusted=True, contradictions=None):
    effective = position if effective is None else effective
    return SimpleNamespace(
        intraday_regime=regime_name,
        position_signal=position,
        raw_position_signal=position,
        effective_position_signal=effective,
        trust_intraday_signals=trusted,
        contradictions=list(contradictions or []),
        reasons=[f"Intraday regime: {regime_name}."],
    )


def asdictish(x):
    if hasattr(x,"as_dict"):
        return x.as_dict()
    if hasattr(x,"__dict__"):
        return dict(vars(x))
    return x


def run(events_path):
    rows=load_events_csv(events_path)

    e15=assess_event_backfill("XHLD",rows,"2026-09-15")["assessment"]
    e16=assess_event_backfill("XHLD",rows,"2026-09-16")["assessment"]
    e21=assess_event_backfill("XHLD",rows,"2026-09-21")["assessment"]

    scenarios=[
        {
            "name":"NO_EVENT_NEUTRAL_NO_POSITION",
            "regime":regime(),
            "event":e15,
            "market":market("NEUTRAL","MIXED"),
            "intraday":intraday("ABOVE_VWAP","CONTINUE"),
        },
        {
            "name":"PARTNERSHIP_SUPPORTIVE_NO_POSITION",
            "regime":regime(),
            "event":e16,
            "market":market("SUPPORTIVE","RISK_ON"),
            "intraday":intraday("OPENING_RANGE_BREAKOUT","CONTINUE"),
        },
        {
            "name":"FINANCING_PLUS_STRONG_PRICE",
            "regime":regime(),
            "event":e21,
            "market":market("SUPPORTIVE","RISK_ON"),
            "intraday":intraday("OPENING_RANGE_BREAKOUT","CONTINUE"),
        },
        {
            "name":"STRONG_STOCK_ADVERSE_MARKET",
            "regime":regime(
                research="MONITOR",
                position="NO_POSITION",
                behavior="FLOW_PERSISTENT",
                flow="FLOW_PERSISTENT",
            ),
            "event":e16,
            "market":market(
                "ADVERSE",
                "RISK_OFF",
                ["Stock strength conflicts with adverse market context."],
            ),
            "intraday":intraday("OPENING_RANGE_BREAKOUT","CONTINUE"),
        },
        {
            "name":"POSITION_INTRADAY_DATA_ISSUE",
            "regime":regime(
                research="MONITOR",
                position="CONTINUE",
                behavior="FLOW_PERSISTENT",
                flow="FLOW_PERSISTENT",
            ),
            "event":e21,
            "market":market("NEUTRAL","MIXED"),
            "intraday":intraday(
                "FAILED_INTRADAY_BREAKOUT",
                "PROTECT_PROFIT",
                effective="DATA_ISSUE",
                trusted=False,
            ),
        },
        {
            "name":"POSITION_CONFIRMED_INTRADAY_DANGER",
            "regime":regime(
                research="MONITOR",
                position="CONTINUE",
                behavior="FLOW_PERSISTENT",
                flow="FLOW_COOLING",
            ),
            "event":e21,
            "market":market("ADVERSE","RISK_OFF"),
            "intraday":intraday(
                "FAILED_INTRADAY_BREAKOUT",
                "PROTECT_PROFIT",
                effective="PROTECT_PROFIT",
                trusted=True,
                contradictions=["Recent breakout failed with trusted intraday data."],
            ),
        },
    ]

    out=[]
    for s in scenarios:
        fused=fuse_point_in_time(
            regime=s["regime"],
            event_risk=s["event"],
            market_context=s["market"],
            intraday=s["intraday"],
        )
        row={
            "name":s["name"],
            "event":{
                "catalyst_regime":getattr(s["event"],"catalyst_regime",None),
                "catalyst_strength":getattr(s["event"],"catalyst_strength",None),
                "structural_risk_level":getattr(s["event"],"structural_risk_level",None),
                "structural_risk_score":getattr(s["event"],"structural_risk_score",None),
                "causality":getattr(s["event"],"catalyst_causality",None),
            },
            "fusion":asdictish(fused),
        }
        out.append(row)

    return out


def main():
    a=argparse.ArgumentParser()
    a.add_argument("--events-csv",default=str(EVENTS_DEFAULT))
    a.add_argument("--out")
    z=a.parse_args()

    out=run(z.events_csv)

    for x in out:
        f=x["fusion"]
        print("\nSCENARIO",x["name"])
        print(" research :",f.get("final_research_state"))
        print(" position :",f.get("final_position_state"))
        print(" setup    :",f.get("setup_family"))
        print(" risk     :",f.get("risk_overlay"))
        print(" context  :",f.get("context_overlay"))
        print(" event    :",f.get("event_overlay"))
        print(" contradictions:")
        for c in f.get("contradictions") or []:
            print("   -",c)

    if z.out:
        Path(z.out).write_text(json.dumps(out,indent=2,default=str))
        print("\nWROTE",z.out)


if __name__=="__main__":
    main()
