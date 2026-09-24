#!/usr/bin/env python3
from pathlib import Path
import argparse, json, csv
from collections import Counter, defaultdict
from statistics import median

WEAK_REGIMES = {
    "FAILED_INTRADAY_BREAKOUT",
    "HIGH_OF_DAY_REJECTION",
    "INTRADAY_BREAKDOWN",
    "BELOW_VWAP",
}
STRONG_REGIMES = {
    "OPENING_RANGE_BREAKOUT",
    "VWAP_RECLAIM_BREAKOUT",
    "ABOVE_VWAP",
}

def episodes(rows, field="intraday_regime"):
    out=[]
    if not rows:
        return out
    cur=rows[0].get(field)
    start=0
    for i in range(1,len(rows)):
        v=rows[i].get(field)
        if v!=cur:
            out.append((cur,start,i-1,i-start))
            cur=v
            start=i
    out.append((cur,start,len(rows)-1,len(rows)-start))
    return out

def session_metrics(d):
    rows=d.get("timeline",[])
    regs=[r.get("intraday_regime") for r in rows if r.get("intraday_regime")]
    eps=episodes(rows)
    weak_bars=sum(r in WEAK_REGIMES for r in regs)
    strong_bars=sum(r in STRONG_REGIMES for r in regs)
    failed_bars=sum(r=="FAILED_INTRADAY_BREAKOUT" for r in regs)
    reject_bars=sum(r=="HIGH_OF_DAY_REJECTION" for r in regs)
    breakdown_bars=sum(r=="INTRADAY_BREAKDOWN" for r in regs)
    max_failed=max([e[3] for e in eps if e[0]=="FAILED_INTRADAY_BREAKOUT"] or [0])
    max_reject=max([e[3] for e in eps if e[0]=="HIGH_OF_DAY_REJECTION"] or [0])
    max_breakdown=max([e[3] for e in eps if e[0]=="INTRADAY_BREAKDOWN"] or [0])

    first_weak=None
    for r in rows:
        if r.get("intraday_regime") in WEAK_REGIMES:
            first_weak=r.get("timestamp")
            break

    return {
        "bars":len(rows),
        "weak_bars":weak_bars,
        "strong_bars":strong_bars,
        "failed_bars":failed_bars,
        "reject_bars":reject_bars,
        "breakdown_bars":breakdown_bars,
        "max_failed_episode":max_failed,
        "max_rejection_episode":max_reject,
        "max_breakdown_episode":max_breakdown,
        "first_weak_timestamp":first_weak,
        "regime_counts":Counter(regs),
    }

def main():
    a=argparse.ArgumentParser()
    a.add_argument("--replay-dir",required=True)
    a.add_argument("--manifest")
    a.add_argument("--json-out")
    z=a.parse_args()

    role={}
    if z.manifest:
        with open(z.manifest,newline="") as f:
            for r in csv.DictReader(f):
                role[(r["symbol"],r["date"])]=r.get("role","")

    rows=[]
    by_symbol=defaultdict(list)

    for p in sorted(Path(z.replay_dir).glob("*.json")):
        with p.open() as f:
            d=json.load(f)
        symbol=d.get("symbol") or p.stem.split("_")[0]
        stem=p.stem
        date=stem[len(symbol)+1:] if stem.startswith(symbol+"_") else ""
        m=session_metrics(d)
        rec={
            "symbol":symbol,
            "date":date,
            "role":role.get((symbol,date),""),
            **{k:v for k,v in m.items() if k!="regime_counts"},
            "regime_counts":dict(m["regime_counts"]),
        }
        rows.append(rec)
        by_symbol[symbol].append(rec)

    print("\n=== V15.7.5 SIGNAL DIAGNOSTICS ===")
    print("sessions:",len(rows))

    for symbol in sorted(by_symbol):
        ss=by_symbol[symbol]
        bars=sum(x["bars"] for x in ss)
        weak=sum(x["weak_bars"] for x in ss)
        strong=sum(x["strong_bars"] for x in ss)
        failed=sum(x["failed_bars"] for x in ss)
        reject=sum(x["reject_bars"] for x in ss)
        breakdown=sum(x["breakdown_bars"] for x in ss)
        sessions_failed=sum(x["failed_bars"]>0 for x in ss)
        sessions_reject=sum(x["reject_bars"]>0 for x in ss)
        sessions_breakdown=sum(x["breakdown_bars"]>0 for x in ss)

        print(f"\n{symbol}")
        print(" sessions                 :",len(ss))
        print(" total bars               :",bars)
        print(" weak-regime bar %        :",round(100*weak/bars,2) if bars else None)
        print(" strong-regime bar %      :",round(100*strong/bars,2) if bars else None)
        print(" failed-breakout bar %    :",round(100*failed/bars,2) if bars else None)
        print(" rejection bar %          :",round(100*reject/bars,2) if bars else None)
        print(" breakdown bar %          :",round(100*breakdown/bars,2) if bars else None)
        print(" sessions w/ failed       :",f"{sessions_failed}/{len(ss)}")
        print(" sessions w/ rejection    :",f"{sessions_reject}/{len(ss)}")
        print(" sessions w/ breakdown    :",f"{sessions_breakdown}/{len(ss)}")
        print(" median max failed episode:",median([x["max_failed_episode"] for x in ss]))
        print(" max failed episode       :",max(x["max_failed_episode"] for x in ss))
        print(" median max reject episode:",median([x["max_rejection_episode"] for x in ss]))
        print(" max reject episode       :",max(x["max_rejection_episode"] for x in ss))

    allregs=Counter()
    for x in rows:
        allregs.update(x["regime_counts"])

    print("\nALL REGIMES")
    for k,v in allregs.most_common():
        print(k,v)

    if z.json_out:
        Path(z.json_out).write_text(json.dumps(rows,indent=2))
        print("\nWROTE",z.json_out)

if __name__=="__main__":
    main()
