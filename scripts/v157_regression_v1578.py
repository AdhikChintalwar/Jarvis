#!/usr/bin/env python3
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

from baby_ui_backend.v157_intraday import assess_intraday

def main():
    base=[
        {"open":10.10,"high":10.30,"low":10.00,"close":10.20,"volume":100},
        {"open":10.20,"high":10.50,"low":10.15,"close":10.40,"volume":120},
        {"open":10.40,"high":10.45,"low":10.10,"close":10.30,"volume":140},
    ]

    # Single shallow support cross: no breakdown event.
    shallow=base+[
        {"open":10.30,"high":10.32,"low":9.97,"close":9.98,"volume":200},
    ]
    x=assess_intraday(shallow,reference_entry_price=10.20)
    assert x.breakdown_event is False, x.as_dict()
    print("PASS shallow_single_cross")

    # Second consecutive close confirms a breakdown.
    confirmed=base+[
        {"open":10.30,"high":10.32,"low":9.97,"close":9.98,"volume":200},
        {"open":9.98,"high":10.00,"low":9.90,"close":9.94,"volume":240},
    ]
    y=assess_intraday(confirmed,reference_entry_price=10.20)
    assert y.breakdown_event is True, y.as_dict()
    assert y.two_closes_below_opening_range is True, y.as_dict()
    print("PASS breakdown_confirmation")

    # Stay below support for many bars. The old bug kept breakdown=True forever.
    stale=confirmed[:]
    for _ in range(6):
        stale.append({
            "open":9.94,"high":9.98,"low":9.88,"close":9.92,"volume":180
        })
    z=assess_intraday(stale,reference_entry_price=10.20,event_window_bars=6)
    assert z.below_opening_range_support is True, z.as_dict()
    assert z.breakdown_event is False, z.as_dict()
    assert z.intraday_regime!="INTRADAY_BREAKDOWN", z.as_dict()
    print("PASS breakdown_event_expires")

    # Fresh decisive break should still trigger.
    decisive=base+[
        {"open":10.30,"high":10.31,"low":9.80,"close":9.84,"volume":300},
    ]
    q=assess_intraday(decisive,reference_entry_price=10.20)
    assert q.breakdown_event is True, q.as_dict()
    print("PASS decisive_breakdown")

    # No-position invariant.
    n=assess_intraday(confirmed)
    assert n.position_signal=="NO_POSITION", n.as_dict()
    print("PASS no_position")

    print("V15.7.8 regression PASS")

if __name__=="__main__":
    main()
