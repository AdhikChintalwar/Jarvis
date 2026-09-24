#!/usr/bin/env python3
from pathlib import Path
import argparse,csv,json
from collections import Counter,defaultdict

RISK={"PROTECT_PROFIT","REVIEW","URGENT_REVIEW","DATA_ISSUE"}

def main():
    a=argparse.ArgumentParser()
    a.add_argument("--manifest",required=True)
    a.add_argument("--replay-dir",default="/tmp/baby_v1574_replays")
    z=a.parse_args()

    meta={}
    with open(z.manifest,newline="") as f:
        for r in csv.DictReader(f):
            meta[(r["symbol"],r["date"])]=r

    replay_dir=Path(z.replay_dir)
    sessions=[]
    for p in sorted(replay_dir.glob("*.json")):
        with p.open() as f:
            d=json.load(f)
        symbol=d.get("symbol")
        stem=p.stem
        date=stem[len(symbol)+1:] if symbol and stem.startswith(symbol+"_") else ""
        m=meta.get((symbol,date),{})
        rows=d.get("timeline",[])
        if not rows:
            continue

        regimes=Counter(x.get("intraday_regime") for x in rows)
        raw=[x.get("raw_position_signal",x.get("position_signal")) for x in rows]
        eff=[x.get("effective_position_signal",x.get("position_signal")) for x in rows]

        first_raw_alert=None
        first_eff_alert=None
        for x in rows:
            rs=x.get("raw_position_signal",x.get("position_signal"))
            es=x.get("effective_position_signal",x.get("position_signal"))
            if first_raw_alert is None and rs in RISK:
                first_raw_alert=(x.get("timestamp"),rs,x.get("intraday_regime"))
            if first_eff_alert is None and es in RISK:
                first_eff_alert=(x.get("timestamp"),es,x.get("intraday_regime"))

        sessions.append({
            "symbol":symbol,
            "date":date,
            "role":m.get("role",""),
            "quality":(d.get("data_quality") or {}).get("quality_state"),
            "first_raw_alert":first_raw_alert,
            "first_effective_alert":first_eff_alert,
            "raw_alert_count":sum(x in RISK for x in raw),
            "effective_alert_count":sum(x in RISK for x in eff),
            "regimes":regimes,
        })

    print("\n=== V15.7.4 BENCHMARK REPORT ===")
    print("sessions:",len(sessions))
    print("quality:",Counter(x["quality"] for x in sessions))
    print("roles:",Counter(x["role"] for x in sessions))

    controls=[x for x in sessions if x["role"]=="CONTROL_NO_POSITION"]
    refs=[x for x in sessions if x["role"]=="REFERENCE_POSITION"]

    # A control without a position should never generate a position-management alert.
    control_bad=[
        x for x in controls
        if x["first_effective_alert"] is not None
    ]
    print("\nCONTROL NO-POSITION")
    print("sessions:",len(controls))
    print("sessions with effective position alert:",len(control_bad))

    print("\nREFERENCE POSITIONS")
    print("sessions:",len(refs))
    for x in refs:
        print(
            x["symbol"],x["date"],
            "quality=",x["quality"],
            "first_alert=",x["first_effective_alert"],
            "alert_count=",x["effective_alert_count"],
        )

    print("\nMOST COMMON INTRADAY REGIMES")
    allregs=Counter()
    for x in sessions:
        allregs.update(x["regimes"])
    for k,v in allregs.most_common(15):
        print(k,v)

    print("\nCONTROL ALERT DETAILS")
    for x in control_bad[:20]:
        print(x["symbol"],x["date"],x["first_effective_alert"])

if __name__=="__main__":
    main()
