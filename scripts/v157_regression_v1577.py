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

    shallow=base+[
        {"open":10.30,"high":10.32,"low":9.97,"close":9.98,"volume":200},
    ]
    x=assess_intraday(shallow,reference_entry_price=10.20)
    assert x.breakdown_event is False, x.as_dict()
    assert x.intraday_regime!="INTRADAY_BREAKDOWN", x.as_dict()
    print("PASS shallow_single_cross")

    persistent=base+[
        {"open":10.30,"high":10.32,"low":9.97,"close":9.98,"volume":200},
        {"open":9.98,"high":10.00,"low":9.90,"close":9.94,"volume":240},
    ]
    y=assess_intraday(persistent,reference_entry_price=10.20)
    assert y.two_closes_below_opening_range is True, y.as_dict()
    assert y.breakdown_event is True, y.as_dict()
    print("PASS persistent_breakdown")

    decisive=base+[
        {"open":10.30,"high":10.31,"low":9.80,"close":9.84,"volume":300},
    ]
    z=assess_intraday(decisive,reference_entry_price=10.20)
    assert z.breakdown_event is True, z.as_dict()
    assert z.breakdown_depth_or_width is not None and z.breakdown_depth_or_width>=0.20, z.as_dict()
    print("PASS decisive_breakdown")

    n=assess_intraday(persistent)
    assert n.position_signal=="NO_POSITION", n.as_dict()
    print("PASS no_position")

    print("V15.7.7 regression PASS")

if __name__=="__main__":
    main()
