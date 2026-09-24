#!/usr/bin/env python3
from pathlib import Path
import argparse,json
from collections import Counter

ALERTS={"PROTECT_PROFIT","REVIEW","URGENT_REVIEW","DATA_ISSUE"}

def main():
    a=argparse.ArgumentParser()
    a.add_argument("files",nargs="+")
    z=a.parse_args()

    total=0
    raw_alerts=0
    effective_alerts=0
    data_issues=0
    regimes=Counter()
    qualities=Counter()

    for fp in z.files:
        p=Path(fp)
        with p.open() as f:
            d=json.load(f)
        rows=d.get("timeline",[])
        q=(d.get("data_quality") or {}).get("quality_state")
        if q:
            qualities[q]+=1

        for r in rows:
            total+=1
            reg=r.get("intraday_regime") or r.get("behavior_regime") or r.get("phase")
            if reg: regimes[reg]+=1

            raw=r.get("raw_position_signal",r.get("position_signal",r.get("position_state")))
            eff=r.get("effective_position_signal",r.get("position_signal",r.get("position_state")))
            if raw in ALERTS: raw_alerts+=1
            if eff in ALERTS: effective_alerts+=1
            if eff=="DATA_ISSUE": data_issues+=1

    print("files:",len(z.files))
    print("rows:",total)
    print("quality:",qualities)
    print("raw alerts:",raw_alerts)
    print("effective alerts:",effective_alerts)
    print("data issues:",data_issues)
    print("top regimes:",regimes.most_common(15))

if __name__=="__main__":
    main()
