#!/usr/bin/env python3
from pathlib import Path
import argparse,json

RISK={"PROTECT_PROFIT","REVIEW","URGENT_REVIEW"}

def main():
    a=argparse.ArgumentParser()
    a.add_argument("--dir",required=True)
    z=a.parse_args()

    print("\n=== REFERENCE SHADOW REPORT ===")
    for p in sorted(Path(z.dir).glob("*.json")):
        with p.open() as f:
            d=json.load(f)
        q=d.get("data_quality") or {}
        rows=d.get("timeline",[])
        first_raw=None
        for x in rows:
            raw=x.get("raw_position_signal",x.get("position_signal"))
            if raw in RISK:
                first_raw=(x.get("timestamp"),raw,x.get("intraday_regime"))
                break

        last=rows[-1] if rows else {}
        print("\n",p.name)
        print(" quality     :",q.get("quality_state"))
        print(" coverage    :",q.get("coverage_ratio"))
        print(" max gap     :",q.get("max_gap_minutes"))
        print(" first raw risk:",first_raw)
        print(" final raw   :",last.get("raw_position_signal"))
        print(" final effective:",last.get("effective_position_signal"))
        print(" final regime:",last.get("intraday_regime"))
        print(" NOTE: shadow-only; data quality prevents calibration use.")

if __name__=="__main__":
    main()
