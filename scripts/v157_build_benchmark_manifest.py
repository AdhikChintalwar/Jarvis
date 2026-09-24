#!/usr/bin/env python3
from pathlib import Path
import argparse,csv

DEFAULT_SYMBOLS=["AAPL","NVDA","SPY","IWM","GME"]

REFERENCE = {
    ("NCI","2026-07-30"): 11.02,
    ("NCI","2026-08-24"): 11.31,
    ("TJGC","2026-09-17"): 10.04,
    ("TJGC","2026-09-18"): 10.04,
    ("XHLD","2026-09-17"): 9.37,
    ("XHLD","2026-09-21"): 9.37,
}

SPECIAL = list(REFERENCE.keys())

def dates_from_csv(path):
    out=[]
    with open(path,newline="") as f:
        for r in csv.DictReader(f):
            d=str(r.get("date") or "")[:10]
            if d:
                out.append(d)
    return out

def main():
    a=argparse.ArgumentParser()
    a.add_argument("--symbols",nargs="*",default=DEFAULT_SYMBOLS)
    a.add_argument("--sessions-per-symbol",type=int,default=10)
    a.add_argument("--out",default="/tmp/baby_v1574_manifest.csv")
    z=a.parse_args()

    rows=[]
    for symbol in z.symbols:
        p=Path(f"data/replay/{symbol}.csv")
        if not p.exists():
            print("SKIP missing",p)
            continue
        dates=dates_from_csv(p)
        if not dates:
            continue

        n=max(1,z.sessions_per_symbol)
        # Spread samples across the available history instead of only taking recent days.
        if len(dates)<=n:
            chosen=dates
        else:
            idxs=sorted(set(round(i*(len(dates)-1)/(n-1)) for i in range(n))) if n>1 else [len(dates)-1]
            chosen=[dates[i] for i in idxs]

        for d in chosen:
            rows.append({
                "symbol":symbol,
                "date":d,
                "daily_csv":str(p),
                "intraday_csv":f"data/replay/intraday/{symbol}_{d}_5m.csv",
                "reference_entry":"",
                "role":"CONTROL_NO_POSITION",
            })

    for symbol,d in SPECIAL:
        p=Path(f"data/replay/{symbol}.csv")
        if not p.exists():
            continue
        rows.append({
            "symbol":symbol,
            "date":d,
            "daily_csv":str(p),
            "intraday_csv":f"data/replay/intraday/{symbol}_{d}_5m.csv",
            "reference_entry":REFERENCE[(symbol,d)],
            "role":"REFERENCE_POSITION",
        })

    # Deduplicate symbol/date, preferring reference-position rows.
    merged={}
    for r in rows:
        k=(r["symbol"],r["date"])
        if k not in merged or r["role"]=="REFERENCE_POSITION":
            merged[k]=r

    out=Path(z.out)
    with out.open("w",newline="") as f:
        w=csv.DictWriter(f,fieldnames=[
            "symbol","date","daily_csv","intraday_csv","reference_entry","role"
        ])
        w.writeheader()
        for r in sorted(merged.values(),key=lambda x:(x["symbol"],x["date"])):
            w.writerow(r)

    print(out)
    print("sessions",len(merged))

if __name__=="__main__":
    main()
