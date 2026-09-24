#!/usr/bin/env python3
from pathlib import Path
from types import SimpleNamespace
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

from baby_ui_backend.v158_event_backfill import (
    load_events_csv,
    point_in_time_events,
    assess_event_backfill,
    fuse_point_in_time,
)

EVENTS=ROOT/"examples/v158_synthetic_events.csv"


def main():
    rows=load_events_csv(EVENTS)

    # ---------------------------------------------------------------
    # 1. Point-in-time event visibility / no lookahead
    # ---------------------------------------------------------------
    e17=point_in_time_events(rows,"XHLD","2026-09-17")
    h17=" | ".join(x["headline"].lower() for x in e17)
    assert "partnership" in h17, e17
    assert "buyback" not in h17, e17
    assert "offering" not in h17, e17
    print("PASS no_lookahead_sep17")

    e18=point_in_time_events(rows,"XHLD","2026-09-18")
    h18=" | ".join(x["headline"].lower() for x in e18)
    assert "partnership" in h18
    assert "buyback" in h18
    assert "offering" not in h18
    print("PASS no_lookahead_sep18")

    e21=point_in_time_events(rows,"XHLD","2026-09-21")
    h21=" | ".join(x["headline"].lower() for x in e21)
    assert "partnership" in h21
    assert "buyback" in h21
    assert "offering" in h21
    print("PASS financing_visible_sep21")

    # ---------------------------------------------------------------
    # 2. Installed event engine actually consumes the backfill.
    # ---------------------------------------------------------------
    r17=assess_event_backfill("XHLD",rows,"2026-09-17")
    a17=r17["assessment"]
    assert r17["visible_event_count"]==1, r17
    assert getattr(a17,"events_seen",0)>=1, a17
    assert getattr(a17,"catalyst_causality","NOT_ESTABLISHED")=="NOT_ESTABLISHED"
    print("PASS event_engine_adapter",r17["engine_container"])

    r21=assess_event_backfill("XHLD",rows,"2026-09-21")
    a21=r21["assessment"]
    assert r21["visible_event_count"]==3, r21
    assert getattr(a21,"events_seen",0)>=3, a21
    assert getattr(a21,"catalyst_causality","NOT_ESTABLISHED")=="NOT_ESTABLISHED"
    print("PASS causality_not_established")

    # Financing should not magically disappear from risk evidence.
    reasons=" ".join(getattr(a21,"structural_risk_reasons",[]) or []).lower()
    headline=str(getattr(a21,"catalyst_headline","") or "").lower()
    assert (
        "financ" in reasons or
        "offering" in reasons or
        "financ" in headline or
        "offering" in headline
    ), (reasons,headline)
    print("PASS financing_risk_visible")

    # ---------------------------------------------------------------
    # 3. Fusion: no position stays no position.
    # ---------------------------------------------------------------
    regime=SimpleNamespace(
        research_state="MONITOR",
        position_state="NO_POSITION",
        behavior_regime="FLOW_PERSISTENT",
        instrument_profile="LIQUID_EQUITY",
        flow_trend="FLOW_PERSISTENT",
        contradictions=[],
        rationale=[],
    )
    market=SimpleNamespace(
        context_signal="SUPPORTIVE",
        market_regime="RISK_ON",
        contradictions=[],
        rationale=[],
    )
    intraday=SimpleNamespace(
        intraday_regime="OPENING_RANGE_BREAKOUT",
        position_signal="CONTINUE",
        effective_position_signal="CONTINUE",
        trust_intraday_signals=True,
        contradictions=[],
        reasons=[],
    )

    fused=fuse_point_in_time(
        regime=regime,
        event_risk=a17,
        market_context=market,
        intraday=intraday,
    )
    assert getattr(fused,"final_position_state",None)=="NO_POSITION", fused
    print("PASS fusion_no_position")

    # ---------------------------------------------------------------
    # 4. Bad intraday data: raw signal cannot override DATA_ISSUE.
    # ---------------------------------------------------------------
    regime2=SimpleNamespace(
        research_state="MONITOR",
        position_state="CONTINUE",
        behavior_regime="FLOW_PERSISTENT",
        instrument_profile="LIQUID_EQUITY",
        flow_trend="FLOW_PERSISTENT",
        contradictions=[],
        rationale=[],
    )
    bad_intraday=SimpleNamespace(
        intraday_regime="FAILED_INTRADAY_BREAKOUT",
        position_signal="PROTECT_PROFIT",
        raw_position_signal="PROTECT_PROFIT",
        effective_position_signal="DATA_ISSUE",
        trust_intraday_signals=False,
        contradictions=[],
        reasons=[],
    )
    fused2=fuse_point_in_time(
        regime=regime2,
        event_risk=a21,
        market_context=market,
        intraday=bad_intraday,
    )
    assert getattr(fused2,"final_position_state",None)=="DATA_ISSUE", fused2
    print("PASS fusion_data_issue_authority")

    print("V15.8.0 regression PASS")


if __name__=="__main__":
    main()
