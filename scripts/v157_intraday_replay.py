#!/usr/bin/env python3
import argparse,csv,json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

from baby_ui_backend.v157_intraday import assess_intraday
from baby_ui_backend.v157_data_quality import assess_intraday_quality


def rows(path):
    out=[]
    with open(path,newline="") as f:
        for r in csv.DictReader(f):
            for k in ("open","high","low","close","volume"):
                try:r[k]=float(r[k])
                except Exception:pass
            out.append(r)
    return out



def daily_row_for_session(path, session_date):
    if not path:
        return {}
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            if str(r.get("date") or "")[:10] == session_date:
                return r
    return {}

def main():
    a=argparse.ArgumentParser()
    a.add_argument("--symbol",required=True)
    a.add_argument("--csv",required=True)
    a.add_argument("--reference-entry",type=float)
    a.add_argument("--opening-range-bars",type=int,default=3)
    a.add_argument("--daily-csv")
    a.add_argument("--feed-scope",default="IEX")
    a.add_argument("--out")
    z=a.parse_args()

    data=rows(z.csv)
    first_ts = str((data[0].get("timestamp") or data[0].get("datetime") or data[0].get("time") or "")) if data else ""
    try:
        from datetime import datetime
        from zoneinfo import ZoneInfo
        dt = datetime.fromisoformat(first_ts.replace("Z","+00:00")).astimezone(ZoneInfo("America/New_York"))
        session_date = dt.date().isoformat()
    except Exception:
        session_date = first_ts[:10]

    daily_ref = daily_row_for_session(z.daily_csv, session_date)
    quality = assess_intraday_quality(data, daily_ref, feed_scope=z.feed_scope)
    timeline=[]
    for i in range(len(data)):
        cur=data[:i+1]
        x=assess_intraday(
            cur,
            reference_entry_price=z.reference_entry,
            opening_range_bars=z.opening_range_bars,
        )
        effective_signal = x.position_signal if quality.trust_intraday_signals else "DATA_ISSUE"
        timeline.append({
            "timestamp":cur[-1].get("timestamp") or cur[-1].get("datetime") or cur[-1].get("time") or str(i),
            "close":cur[-1].get("close"),
            **x.as_dict(),
            "raw_position_signal":x.position_signal,
            "effective_position_signal":effective_signal,
            "data_quality_state":quality.quality_state,
            "trust_intraday_signals":quality.trust_intraday_signals,
        })

    result={"symbol":z.symbol,"data_quality":quality.as_dict(),"timeline":timeline}
    text=json.dumps(result,indent=2)
    if z.out:
        Path(z.out).write_text(text)
        print(z.out)
    else:
        print(text)


if __name__=="__main__":
    main()
