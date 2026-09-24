#!/usr/bin/env python3
from pathlib import Path
import argparse,csv,json,subprocess

def load_audit(path):
    with open(path) as f:
        a=json.load(f)
    return {(x["symbol"],x["date"]):x for x in a}

def main():
    a=argparse.ArgumentParser()
    a.add_argument("--manifest",required=True)
    a.add_argument("--audit-json",required=True)
    a.add_argument("--out-dir",default="/tmp/baby_v1575_shadow_refs")
    z=a.parse_args()

    audit=load_audit(z.audit_json)
    outdir=Path(z.out_dir)
    outdir.mkdir(parents=True,exist_ok=True)

    with open(z.manifest,newline="") as f:
        rows=list(csv.DictReader(f))

    ran=0
    for r in rows:
        if r.get("role")!="REFERENCE_POSITION":
            continue
        symbol=r["symbol"].upper()
        date=r["date"]
        q=(audit.get((symbol,date)) or {}).get("quality_state","MISSING")
        if q not in {"LIMITED","UNTRUSTED"}:
            continue

        out=outdir/f"{symbol}_{date}.json"
        cmd=[
            "python3","scripts/v157_intraday_replay.py",
            "--symbol",symbol,
            "--csv",r["intraday_csv"],
            "--daily-csv",r["daily_csv"],
            "--feed-scope","IEX",
            "--opening-range-bars","3",
            "--reference-entry",r["reference_entry"],
            "--out",str(out),
        ]
        subprocess.run(cmd,check=True)
        print("SHADOW",symbol,date,"quality=",q,out)
        ran+=1

    print("shadow sessions",ran)

if __name__=="__main__":
    main()
