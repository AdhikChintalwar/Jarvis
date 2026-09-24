from __future__ import annotations

from dataclasses import dataclass, asdict


@dataclass
class UnifiedResearchSnapshot:
    final_research_state:str="DISCOVERY"
    final_position_state:str="NO_POSITION"
    setup_family:str="UNKNOWN"
    risk_overlay:str="NORMAL"
    context_overlay:str="NEUTRAL"
    event_overlay:str="NONE"
    evidence:list[str]|None=None
    contradictions:list[str]|None=None

    def as_dict(self):
        return asdict(self)


POSITION_PRIORITY = {
    "DATA_ISSUE": 5,
    "URGENT_REVIEW": 4,
    "PROTECT_PROFIT": 3,
    "REVIEW": 2,
    "CONTINUE": 1,
    "NO_POSITION": 0,
}


def fuse(
    regime=None,
    event_risk=None,
    market_context=None,
    intraday=None,
):
    regime = regime or {}
    event_risk = event_risk or {}
    market_context = market_context or {}
    intraday = intraday or {}

    def g(obj, key, default=None):
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)

    research = g(regime, "research_state", "DISCOVERY")
    position = g(regime, "position_state", "NO_POSITION")
    behavior = g(regime, "behavior_regime", "UNKNOWN")
    catalyst = g(event_risk, "catalyst_regime", "NONE")
    structural = g(event_risk, "structural_risk_level", "LOW")
    context = g(market_context, "context_signal", "NEUTRAL")
    intra_regime = g(intraday, "intraday_regime", "INSUFFICIENT_DATA")
    intra_position = g(intraday, "position_signal", "NO_POSITION")

    # Event-driven setup family overrides ordinary technical family.
    if catalyst and catalyst not in {"NONE","OTHER_EVENT","STRUCTURAL_EVENT"}:
        setup_family = catalyst
    else:
        setup_family = behavior or "UNKNOWN"

    if structural == "CRITICAL":
        risk_overlay = "CRITICAL_STRUCTURAL_RISK"
    elif structural == "HIGH":
        risk_overlay = "HIGH_STRUCTURAL_RISK"
    elif structural == "MODERATE":
        risk_overlay = "MODERATE_STRUCTURAL_RISK"
    else:
        risk_overlay = "NORMAL"

    # Position state is conservative across daily + intraday.
    candidates=[position, intra_position]
    final_position=max(
        candidates,
        key=lambda x: POSITION_PRIORITY.get(str(x or "").upper(), -1)
    )

    # Never turn NO_POSITION into a holding instruction.
    if position=="NO_POSITION":
        final_position="NO_POSITION"

    evidence=[
        f"Behavior regime: {behavior}.",
        f"Setup family: {setup_family}.",
        f"Structural risk: {structural}.",
        f"Market context: {context}.",
        f"Intraday regime: {intra_regime}.",
    ]

    contradictions=[]
    if structural in {"HIGH","CRITICAL"} and catalyst not in {"NONE","STRUCTURAL_EVENT","OTHER_EVENT"}:
        contradictions.append("Catalyst strength coexists with elevated structural risk.")
    if context in {"ADVERSE","MILDLY_ADVERSE"} and behavior in {"EXPANSION","MOMENTUM_EXPANSION","RE_ACCUMULATION"}:
        contradictions.append("Stock strength is occurring against adverse market context.")
    if intra_regime in {"FAILED_INTRADAY_BREAKOUT","HIGH_OF_DAY_REJECTION","INTRADAY_BREAKDOWN"} and behavior in {"EXPANSION","MOMENTUM_EXPANSION","CLIMACTIC_EXPANSION"}:
        contradictions.append("Daily strength conflicts with intraday deterioration.")

    return UnifiedResearchSnapshot(
        final_research_state=research,
        final_position_state=final_position,
        setup_family=setup_family,
        risk_overlay=risk_overlay,
        context_overlay=context,
        event_overlay=catalyst,
        evidence=evidence,
        contradictions=contradictions,
    )
