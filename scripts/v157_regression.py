#!/usr/bin/env python3
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

from baby_ui_backend.v157_intraday import assess_intraday
from baby_ui_backend.v157_fusion import fuse


def assert_eq(a,b,msg):
    if a!=b:
        raise AssertionError(f"{msg}: expected {b}, got {a}")


def test_no_position():
    bars=[
        {"open":10,"high":10.2,"low":9.9,"close":10.1,"volume":100},
        {"open":10.1,"high":10.3,"low":10.0,"close":10.2,"volume":120},
        {"open":10.2,"high":10.4,"low":10.1,"close":10.3,"volume":140},
    ]
    x=assess_intraday(bars)
    assert_eq(x.position_signal,"NO_POSITION","no-position invariant")


def test_failed_breakout():
    bars=[
        {"open":10.0,"high":10.2,"low":9.95,"close":10.15,"volume":100000},
        {"open":10.15,"high":10.35,"low":10.10,"close":10.30,"volume":130000},
        {"open":10.30,"high":10.45,"low":10.25,"close":10.40,"volume":160000},
        {"open":10.40,"high":10.80,"low":10.38,"close":10.70,"volume":220000},
        {"open":10.70,"high":10.90,"low":10.55,"close":10.60,"volume":260000},
        {"open":10.60,"high":10.65,"low":10.30,"close":10.35,"volume":320000},
        {"open":10.35,"high":10.40,"low":10.10,"close":10.15,"volume":400000},
    ]
    x=assess_intraday(bars, reference_entry_price=9.8, opening_range_bars=3)
    if x.intraday_regime not in {"FAILED_INTRADAY_BREAKOUT","HIGH_OF_DAY_REJECTION","INTRADAY_BREAKDOWN"}:
        raise AssertionError(f"expected deterioration regime, got {x.intraday_regime}")
    if x.position_signal not in {"PROTECT_PROFIT","REVIEW"}:
        raise AssertionError(f"expected protective position state, got {x.position_signal}")


def test_fusion_no_position():
    x=fuse(
        regime={"research_state":"MONITOR","position_state":"NO_POSITION","behavior_regime":"MOMENTUM_EXPANSION"},
        event_risk={"catalyst_regime":"EVENT_DRIVEN_CONTRACT","structural_risk_level":"LOW"},
        market_context={"context_signal":"SUPPORTIVE"},
        intraday={"intraday_regime":"OPENING_RANGE_BREAKOUT","position_signal":"NO_POSITION"},
    )
    assert_eq(x.final_position_state,"NO_POSITION","fusion no-position invariant")


def test_structural_overlay():
    x=fuse(
        regime={"research_state":"MONITOR","position_state":"CONTINUE","behavior_regime":"EXPANSION"},
        event_risk={"catalyst_regime":"EVENT_DRIVEN_CONTRACT","structural_risk_level":"HIGH"},
        market_context={"context_signal":"NEUTRAL"},
        intraday={"intraday_regime":"ABOVE_VWAP","position_signal":"CONTINUE"},
    )
    assert_eq(x.risk_overlay,"HIGH_STRUCTURAL_RISK","structural risk overlay")


def main():
    tests=[
        test_no_position,
        test_failed_breakout,
        test_fusion_no_position,
        test_structural_overlay,
    ]
    for t in tests:
        t()
        print("PASS",t.__name__)
    print("V15.7 regression PASS")


if __name__=="__main__":
    main()
