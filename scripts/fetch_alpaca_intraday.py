#!/usr/bin/env python3
"""
Fetch 5-minute Alpaca historical bars using standard-library HTTP.

Expected env vars (first matching pair is used):
  APCA_API_KEY_ID / APCA_API_SECRET_KEY
  ALPACA_API_KEY / ALPACA_API_SECRET

Usage:
python3 scripts/fetch_alpaca_intraday.py \
  --symbol AAPL \
  --start 2026-09-21T09:30:00-04:00 \
  --end   2026-09-21T16:00:00-04:00 \
  --out data/replay/AAPL_2026-09-21_5m.csv
"""
import argparse,csv,json,os,urllib.parse,urllib.request
from pathlib import Path

def keypair():
    pairs=[
        ("APCA_API_KEY_ID","APCA_API_SECRET_KEY"),
        ("ALPACA_API_KEY","ALPACA_API_SECRET"),
    ]
    for a,b in pairs:
        if os.getenv(a) and os.getenv(b):
            return os.getenv(a),os.getenv(b)
    raise SystemExit("Missing Alpaca data API credentials in environment.")

def main():
    a=argparse.ArgumentParser()
    a.add_argument("--symbol",required=True)
    a.add_argument("--start",required=True)
    a.add_argument("--end",required=True)
    a.add_argument("--timeframe",default="5Min")
    a.add_argument("--feed",default="iex")
    a.add_argument("--out",required=True)
    z=a.parse_args()

    key,secret=keypair()
    base=f"https://data.alpaca.markets/v2/stocks/{z.symbol.upper()}/bars"
    params={
        "timeframe":z.timeframe,
        "start":z.start,
        "end":z.end,
        "adjustment":"raw",
        "feed":z.feed,
        "limit":"10000",
    }
    url=base+"?"+urllib.parse.urlencode(params)
    req=urllib.request.Request(
        url,
        headers={
            "APCA-API-KEY-ID":key,
            "APCA-API-SECRET-KEY":secret,
        },
    )
    with urllib.request.urlopen(req,timeout=30) as resp:
        payload=json.loads(resp.read().decode("utf-8"))

    bars=payload.get("bars") or []
    out=Path(z.out)
    out.parent.mkdir(parents=True,exist_ok=True)
    with out.open("w",newline="") as f:
        w=csv.writer(f)
        w.writerow(["timestamp","open","high","low","close","volume"])
        for b in bars:
            w.writerow([b.get("t"),b.get("o"),b.get("h"),b.get("l"),b.get("c"),b.get("v")])
    print(out)
    print("bars",len(bars))

if __name__=="__main__":
    main()
