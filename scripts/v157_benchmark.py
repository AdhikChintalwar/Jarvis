#!/usr/bin/env python3
import argparse,json
from pathlib import Path
from collections import Counter

def main():
    a=argparse.ArgumentParser()
    a.add_argument("files",nargs="+")
    z=a.parse_args()

    for path in z.files:
        p=Path(path)
        with p.open() as f:
            d=json.load(f)

        rows=d.get("timeline",[])
        print("\n"+"="*90)
        print(p.name)
        print("="*90)

        for field in [
            "phase","behavior_regime","research_state","position_state",
            "flow_trend","catalyst_regime","structural_risk_level",
            "market_regime","context_signal","intraday_regime","position_signal",
        ]:
            vals=[r.get(field) for r in rows if r.get(field) is not None]
            if vals:
                print(field, Counter(vals))

        alerts=[
            r for r in rows
            if r.get("position_state") in {"PROTECT_PROFIT","REVIEW","URGENT_REVIEW","DATA_ISSUE"}
            or r.get("position_signal") in {"PROTECT_PROFIT","REVIEW","URGENT_REVIEW","DATA_ISSUE"}
        ]
        print("alerts:",len(alerts))
        for r in alerts[-10:]:
            print(
                r.get("date") or r.get("timestamp"),
                r.get("position_state") or r.get("position_signal"),
                r.get("phase") or r.get("intraday_regime"),
            )

if __name__=="__main__":
    main()
