#!/usr/bin/env python3
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

from scripts.v1581_fusion_scenarios import run

def by_name(rows,name):
    for x in rows:
        if x["name"]==name:
            return x
    raise AssertionError(name)

def fusion(x):
    return x["fusion"]

def structural_risk_level(value):
    """
    Normalize fusion overlay labels without changing engine behavior.

    Current fusion can emit labels such as:
      MODERATE_STRUCTURAL_RISK
      HIGH_STRUCTURAL_RISK
      CRITICAL_STRUCTURAL_RISK

    Older regression expected plain MODERATE/HIGH/CRITICAL.
    """
    s=str(value or "").upper().strip()
    for level in ("CRITICAL","HIGH","MODERATE","LOW"):
        if level in s:
            return level
    return s

def main():
    rows=run(ROOT/"examples/v158_synthetic_events.csv")

    a=fusion(by_name(rows,"NO_EVENT_NEUTRAL_NO_POSITION"))
    assert a["final_position_state"]=="NO_POSITION", a
    print("PASS no_event_no_position")

    b=fusion(by_name(rows,"PARTNERSHIP_SUPPORTIVE_NO_POSITION"))
    assert b["final_position_state"]=="NO_POSITION", b
    assert b["event_overlay"] not in {None,"NONE","UNKNOWN"}, b
    print("PASS event_overlay_visible")

    c=by_name(rows,"FINANCING_PLUS_STRONG_PRICE")
    cf=fusion(c)
    assert c["event"]["causality"]=="NOT_ESTABLISHED", c
    assert c["event"]["structural_risk_level"] in {"MODERATE","HIGH","CRITICAL"}, c
    assert structural_risk_level(cf["risk_overlay"]) in {"MODERATE","HIGH","CRITICAL"}, cf
    assert cf["event_overlay"]=="EVENT_DRIVEN_FINANCING", cf
    print("PASS financing_risk_overlay")

    d=fusion(by_name(rows,"STRONG_STOCK_ADVERSE_MARKET"))
    assert d["final_position_state"]=="NO_POSITION", d
    text=" ".join(d.get("contradictions") or []).lower()
    assert (
        "adverse" in text
        or "market" in text
        or str(d.get("context_overlay") or "").upper() in {"ADVERSE","RISK_OFF"}
    ), d
    print("PASS adverse_context_surfaces")

    e=fusion(by_name(rows,"POSITION_INTRADAY_DATA_ISSUE"))
    assert e["final_position_state"]=="DATA_ISSUE", e
    print("PASS data_issue_beats_raw_signal")

    f=fusion(by_name(rows,"POSITION_CONFIRMED_INTRADAY_DANGER"))
    assert f["final_position_state"] in {"PROTECT_PROFIT","REVIEW","URGENT_REVIEW"}, f
    assert f["final_position_state"]!="CONTINUE", f
    print("PASS trusted_intraday_danger_surfaces")

    for name in [
        "NO_EVENT_NEUTRAL_NO_POSITION",
        "PARTNERSHIP_SUPPORTIVE_NO_POSITION",
        "FINANCING_PLUS_STRONG_PRICE",
        "STRONG_STOCK_ADVERSE_MARKET",
    ]:
        x=fusion(by_name(rows,name))
        assert x["final_position_state"]=="NO_POSITION", (name,x)
    print("PASS no_position_matrix")

    print("V15.8.1a regression PASS")

if __name__=="__main__":
    main()
