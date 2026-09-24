#!/usr/bin/env python3
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

from scripts.v1581_fusion_scenarios import run

def by_name(rows,name):
    for x in rows:
        if x["name"]==name:
            return x["fusion"]
    raise AssertionError(name)

def joined(x):
    return " ".join(x.get("contradictions") or []).lower()

def main():
    rows=run(ROOT/"examples/v158_synthetic_events.csv")

    a=by_name(rows,"NO_EVENT_NEUTRAL_NO_POSITION")
    assert a["final_position_state"]=="NO_POSITION", a
    print("PASS no_event_state_unchanged")

    b=by_name(rows,"FINANCING_PLUS_STRONG_PRICE")
    t=joined(b)
    assert "financing" in t or "capital-structure" in t or "structural risk" in t, b
    assert "does not establish" in t or "caused" in t or "caus" in t, b
    assert b["final_position_state"]=="NO_POSITION", b
    print("PASS financing_contradiction")

    c=by_name(rows,"STRONG_STOCK_ADVERSE_MARKET")
    t=joined(c)
    assert "adverse" in t and ("market" in t or "broader" in t), c
    assert c["final_position_state"]=="NO_POSITION", c
    print("PASS adverse_market_contradiction")

    d=by_name(rows,"POSITION_INTRADAY_DATA_ISSUE")
    t=joined(d)
    assert d["final_position_state"]=="DATA_ISSUE", d
    assert "data quality" in t or "not trusted" in t or "data_issue" in t, d
    print("PASS data_issue_explanation")

    e=by_name(rows,"POSITION_CONFIRMED_INTRADAY_DANGER")
    assert e["final_position_state"] in {"PROTECT_PROFIT","REVIEW","URGENT_REVIEW"}, e
    assert len(joined(e))>0, e
    print("PASS danger_contradictions_preserved")

    print("V15.8.2 regression PASS")

if __name__=="__main__":
    main()
