#!/usr/bin/env python3
from pathlib import Path
import argparse,csv,json,subprocess,sys

def load_audit(path):
    with open(path) as f:
        rows=json.load(f)
    return {(x["symbol"],x["date"]):x for x in rows}

def main():
    a=argparse.ArgumentParser()
    a.add_argument("--manifest",required=True)
    a.add_argument("--audit-json",required=True)
    a.add_argument("--out-dir",default="/tmp/baby_v1574_replays")
    a.add_argument("--include-limited",action="store_true")
    z=a.parse_args()

    audit=load_audit(z.audit_json)
    outdir=Path(z.out_dir)
    outdir.mkdir(parents=True,exist_ok=True)

    with open(z.manifest,newline="") as f:
        rows=list(csv.DictReader(f))

    ran=0
    skipped=0
    for r in rows:
        symbol=r["symbol"].strip().upper()
        date=r["date"].strip()
        q=(audit.get((symbol,date)) or {}).get("quality_state","MISSING")
        allowed={"TRUSTED"}
        if z.include_limited:
            allowed.add("LIMITED")

        if q not in allowed:
            print("SKIP",symbol,date,"quality=",q)
            skipped+=1
            continue

        intraday=r["intraday_csv"]
        daily=r["daily_csv"]
        out=outdir/f"{symbol}_{date}.json"
        cmd=[
            "python3","scripts/v157_intraday_replay.py",
            "--symbol",symbol,
            "--csv",intraday,
            "--daily-csv",daily,
            "--feed-scope","IEX",
            "--opening-range-bars","3",
            "--out",str(out),
        ]
        ref=str(r.get("reference_entry") or "").strip()
        if ref:
            cmd += ["--reference-entry",ref]

        subprocess.run(cmd,check=True)
        print("RAN",symbol,date,q,out)
        ran+=1

    print("ran",ran,"skipped",skipped)

if __name__=="__main__":
    main()
