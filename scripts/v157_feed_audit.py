#!/usr/bin/env python3
from pathlib import Path
import argparse,csv,json,sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from baby_ui_backend.v157_data_quality import assess_intraday_quality

def load_intraday(path):
    out=[]
    with open(path,newline="") as f:
        for r in csv.DictReader(f):
            for k in ("open","high","low","close","volume"):
                try:r[k]=float(r[k])
                except Exception:pass
            out.append(r)
    return out

def daily_row(path,date):
    if not path or not Path(path).exists():
        return {}
    with open(path,newline="") as f:
        for r in csv.DictReader(f):
            if str(r.get("date") or "")[:10]==date:
                return r
    return {}

def main():
    a=argparse.ArgumentParser()
    a.add_argument("--manifest",required=True)
    a.add_argument("--json-out")
    a.add_argument("--feed-scope",default="IEX")
    z=a.parse_args()

    results=[]
    with open(z.manifest,newline="") as f:
        rows=list(csv.DictReader(f))

    print("symbol,date,quality,bars,coverage,max_gap,volume_capture,close_diff,high_diff,low_diff")
    for r in rows:
        symbol=r["symbol"].strip().upper()
        date=r["date"].strip()
        intraday_path=r.get("intraday_csv") or r.get("out") or f"data/replay/intraday/{symbol}_{date}_5m.csv"
        daily_path=r.get("daily_csv") or f"data/replay/{symbol}.csv"

        if not Path(intraday_path).exists():
            print(f"{symbol},{date},MISSING,0,,,,,,,")
            results.append({"symbol":symbol,"date":date,"quality_state":"MISSING"})
            continue

        q=assess_intraday_quality(load_intraday(intraday_path),daily_row(daily_path,date),feed_scope=z.feed_scope)
        d=q.as_dict()
        d.update({"symbol":symbol,"date":date,"intraday_csv":intraday_path,"daily_csv":daily_path})
        results.append(d)

        print(",".join(map(str,[
            symbol,date,d["quality_state"],d["regular_session_bars"],d["coverage_ratio"],
            d["max_gap_minutes"],d["volume_capture_ratio"],d["close_difference_pct"],
            d["high_difference_pct"],d["low_difference_pct"],
        ])))

    if z.json_out:
        Path(z.json_out).write_text(json.dumps(results,indent=2))
        print("\nWROTE",z.json_out)

    counts={}
    for x in results:
        counts[x.get("quality_state","UNKNOWN")]=counts.get(x.get("quality_state","UNKNOWN"),0)+1
    print("\nQUALITY COUNTS",counts)

if __name__=="__main__":
    main()
