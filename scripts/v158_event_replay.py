#!/usr/bin/env python3
from pathlib import Path
import argparse,csv,json,sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

from baby_ui_backend.v158_event_backfill import load_events_csv, assess_event_backfill


def daily_rows(path):
    out=[]
    with open(path,newline="") as f:
        for r in csv.DictReader(f):
            out.append(r)
    return sorted(out,key=lambda x:str(x.get("date") or ""))


def main():
    a=argparse.ArgumentParser()
    a.add_argument("--symbol",required=True)
    a.add_argument("--daily-csv",required=True)
    a.add_argument("--events-csv",required=True)
    a.add_argument("--start-date")
    a.add_argument("--end-date")
    a.add_argument("--out")
    z=a.parse_args()

    bars=daily_rows(z.daily_csv)
    events=load_events_csv(z.events_csv)

    timeline=[]
    for r in bars:
        d=str(r.get("date") or "")[:10]
        if not d:
            continue
        if z.start_date and d<z.start_date:
            continue
        if z.end_date and d>z.end_date:
            continue

        x=assess_event_backfill(z.symbol,events,d)
        ev=x["assessment"]

        timeline.append({
            "date":d,
            "close":r.get("close"),
            "visible_event_count":x["visible_event_count"],
            "engine_container":x["engine_container"],
            "catalyst_regime":getattr(ev,"catalyst_regime",None),
            "catalyst_strength":getattr(ev,"catalyst_strength",None),
            "catalyst_source_tier":getattr(ev,"catalyst_source_tier",None),
            "catalyst_headline":getattr(ev,"catalyst_headline",None),
            "catalyst_published_at":getattr(ev,"catalyst_published_at",None),
            "catalyst_causality":getattr(ev,"catalyst_causality",None),
            "structural_risk_level":getattr(ev,"structural_risk_level",None),
            "structural_risk_score":getattr(ev,"structural_risk_score",None),
            "structural_risk_reasons":getattr(ev,"structural_risk_reasons",None),
            "events_seen":getattr(ev,"events_seen",None),
            "primary_events_seen":getattr(ev,"primary_events_seen",None),
            "latest_event_time":getattr(ev,"latest_event_time",None),
            "conflicting_evidence":getattr(ev,"conflicting_evidence",None),
        })

    result={
        "symbol":z.symbol.upper(),
        "timeline":timeline,
        "note":"Daily replay is point-in-time by date; date-only as_of is end-of-day and is not minute-perfect.",
    }

    txt=json.dumps(result,indent=2,default=str)
    if z.out:
        Path(z.out).write_text(txt)
        print(z.out)
    else:
        print(txt)


if __name__=="__main__":
    main()
