#!/usr/bin/env python3
from pathlib import Path
import argparse, csv, os, subprocess

def load_env(path):
    vals={}
    p=Path(path)
    if not p.exists():
        return vals
    for line in p.read_text().splitlines():
        line=line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k,v=line.split("=",1)
        vals[k.strip().lstrip("\\")]=v.strip().strip('"').strip("'")
    return vals

def main():
    a=argparse.ArgumentParser()
    a.add_argument("--manifest",required=True)
    a.add_argument("--env-file",default=".env")
    a.add_argument("--feed",default="iex")
    z=a.parse_args()

    vals=load_env(z.env_file)
    key=vals.get("ALPACA_PAPER_API_KEY") or vals.get("ALPACA_API_KEY") or os.getenv("ALPACA_API_KEY")
    sec=vals.get("ALPACA_PAPER_SECRET_KEY") or vals.get("ALPACA_API_SECRET") or os.getenv("ALPACA_API_SECRET")
    if not key or not sec:
        raise SystemExit("Could not find Alpaca credentials in .env/environment.")

    env=os.environ.copy()
    env["ALPACA_API_KEY"]=key
    env["ALPACA_API_SECRET"]=sec

    with open(z.manifest,newline="") as f:
        rows=list(csv.DictReader(f))

    for r in rows:
        symbol=r["symbol"].strip().upper()
        date=r["date"].strip()
        out=r.get("out") or f"data/replay/intraday/{symbol}_{date}_5m.csv"
        cmd=[
            "python3","scripts/fetch_alpaca_intraday.py",
            "--symbol",symbol,
            "--start",f"{date}T09:30:00-04:00",
            "--end",f"{date}T16:00:00-04:00",
            "--timeframe","5Min",
            "--feed",z.feed,
            "--out",out,
        ]
        print("\nFETCH",symbol,date,"feed=",z.feed)
        try:
            subprocess.run(cmd,env=env,check=True)
        except subprocess.CalledProcessError as e:
            print("FAILED",symbol,date,"exit=",e.returncode)

if __name__=="__main__":
    main()
