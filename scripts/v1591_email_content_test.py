#!/usr/bin/env python3
from pathlib import Path
from types import SimpleNamespace
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from baby_ui_backend.v155_email import build_email

def main():
    x=SimpleNamespace(
        symbol="TEST",stage="MONITOR",phase="ACCUMULATION",setup_type="FLOW_ONLY",
        monitoring_signal="CONTINUE",evidence_score=61,
        observed_facts=["Price is above the recent low.","Flow persistence is constructive."],
        interpretation=["Current evidence supports monitoring, not prediction."],
        contradicting_evidence=["No confirmed catalyst is established."],
        next_conditions=["Require stronger close quality before upgrading."],
        flow=SimpleNamespace(
            label="CONSTRUCTIVE",rvol_20=1.4,dollar_volume=12500000,
            persistence_5=4,up_down_volume_ratio_5=1.8,
            weighted_clv_5=0.42,retention_20=0.71,atr_pct=3.2
        ),
        catalyst=SimpleNamespace(
            headline=None,event_type="NONE",strength="NONE",
            source_tier="NONE",causality="NOT_ESTABLISHED"
        ),
        capital_risk=SimpleNamespace(level="LOW",reasons=[]),
    )

    context={
        "market_regime":"MIXED",
        "broad_market_trend":"ABOVE_TREND",
        "context_signal":"NEUTRAL",
        "contradictions":["Stock strength is occurring in mixed market context."],
    }

    _,text,_=build_email(x,"MONITORING_STARTED",context)

    for label in [
        "OBSERVED FACTS","WHY BABY NOTICED / WHAT CHANGED","CATALYST / NEWS",
        "PRICE + FLOW","CAPITAL STRUCTURE RISK","MARKET CONTEXT",
        "BABY INTERPRETATION","CONTRADICTING EVIDENCE","NEXT CONDITION TO WATCH",
        "WHAT WOULD MAKE BABY CHANGE ITS MIND","STATUS:"
    ]:
        assert label in text,label

    low=text.lower()
    for word in [
        "account balance","paper cash","server-sized shares",
        "proposed_quantity","risk dollars"
    ]:
        assert word not in low,word

    assert "NOT_ESTABLISHED" in text
    assert "Quantity is USER_SELECTED" in text
    assert "No order is placed by email" in text

    _,text2,_=build_email(x,"MONITORING_STARTED",None)
    assert "Baby does not infer it" in text2

    print("PASS required_sections")
    print("PASS sensitive_fields_omitted")
    print("PASS causality_preserved")
    print("PASS market_context_no_invention")
    print("V15.9.1a email content test PASS")

if __name__=="__main__":
    main()
