from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import sqlite3

from .v155_intelligence import analyze as _base_analyze
from .v15101_capital_risk import evaluate_structured_capital_risk


def _f(v, default=None):
    try:
        x = float(v)
        return x if x == x and abs(x) != float("inf") else default
    except Exception:
        return default


def _u(v):
    return str(v or "").strip().upper()


def _b(v):
    if isinstance(v, bool):
        return v
    return _u(v) in {"1", "TRUE", "YES", "Y"}


def _scanner_flow_label(candidate):
    c = candidate or {}
    flow_type = _u(c.get("flow_type"))
    flow_score = _f(c.get("flow_score"))
    rvol = _f(c.get("relative_volume"))
    rvol3 = _f(c.get("rvol_3d_average"))
    high_days = int(_f(c.get("high_volume_days_5d"), 0) or 0)
    close_loc = _f(c.get("close_location_pct"))
    updown = _f(c.get("up_down_volume_ratio_20d"))

    votes = 0
    if flow_type in {"STRONG_ACCUMULATION", "STRONG", "ACCUMULATION"}:
        votes += 2
    elif flow_type in {"BULLISH_FLOW", "CONSTRUCTIVE", "POSITIVE_FLOW"}:
        votes += 1
    if flow_score is not None and flow_score >= 80:
        votes += 2
    elif flow_score is not None and flow_score >= 65:
        votes += 1
    if rvol is not None and rvol >= 1.5:
        votes += 1
    if rvol3 is not None and rvol3 >= 1.5:
        votes += 1
    if high_days >= 2:
        votes += 1
    if updown is not None and updown >= 1.5:
        votes += 1
    if close_loc is not None and close_loc >= 65:
        votes += 1

    if votes >= 6:
        return "STRONG"
    if votes >= 4:
        return "CONSTRUCTIVE"
    if votes >= 2:
        return "MIXED"
    return "WEAK"


def _scanner_phase(candidate, flow_label):
    c = candidate or {}
    breakout = _b(c.get("breakout_20d"))
    breakdown = _b(c.get("breakdown_20d"))
    close_loc = _f(c.get("close_location_pct"))
    ret5 = _f(c.get("return_5d_pct"))
    dist20 = _f(c.get("distance_ema20_pct"))
    rsi = _f(c.get("rsi_14"))

    if breakdown:
        return "RESET"
    if breakout and flow_label in {"STRONG", "CONSTRUCTIVE"}:
        return "EXPANSION"
    if flow_label in {"STRONG", "CONSTRUCTIVE"} and close_loc is not None and close_loc >= 55:
        return "RE_ACCUMULATION"
    if ret5 is not None and ret5 > 20 and dist20 is not None and dist20 > 20:
        return "EXTENDED"
    if rsi is not None and rsi >= 75 and dist20 is not None and dist20 > 15:
        return "EXTENDED"
    if flow_label == "MIXED":
        return "CONSOLIDATION"
    return "ACCUMULATION"


def _setup_type(candidate, phase, flow_label, catalyst_strength):
    if _b((candidate or {}).get("breakout_20d")) and flow_label in {"STRONG", "CONSTRUCTIVE"}:
        return "BREAKOUT"
    if catalyst_strength in {"MEDIUM", "HIGH"} and flow_label in {"STRONG", "CONSTRUCTIVE"}:
        return "FLOW_CATALYST"
    if flow_label in {"STRONG", "CONSTRUCTIVE"}:
        return "FLOW_ONLY"
    if phase in {"RE_ACCUMULATION", "CONSOLIDATION"}:
        return "TECHNICAL_RECOVERY"
    return "NO_CLEAR_CATALYST"


class OpportunityTrajectoryStore:
    def __init__(self, path="data/baby_ui.db"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _db(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        return db

    def _init(self):
        with self._db() as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS v1510_opportunity_trajectory(
                    symbol TEXT NOT NULL,
                    observation_date TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    price REAL,
                    opportunity_score REAL,
                    flow_score REAL,
                    flow_type TEXT,
                    relative_volume REAL,
                    rvol_3d_average REAL,
                    high_volume_days_5d INTEGER,
                    close_location_pct REAL,
                    return_5d_pct REAL,
                    breakout_20d INTEGER,
                    PRIMARY KEY(symbol, observation_date)
                )
            """)
            db.commit()

    def record(self, symbol, candidate):
        c = candidate or {}
        now = datetime.now(timezone.utc)
        vals = (
            _u(symbol), now.date().isoformat(), now.isoformat(),
            _f(c.get("price")), _f(c.get("opportunity_score")), _f(c.get("flow_score")),
            _u(c.get("flow_type")) or None, _f(c.get("relative_volume")),
            _f(c.get("rvol_3d_average")), int(_f(c.get("high_volume_days_5d"), 0) or 0),
            _f(c.get("close_location_pct")), _f(c.get("return_5d_pct")),
            1 if _b(c.get("breakout_20d")) else 0,
        )
        with self._db() as db:
            db.execute("""
                INSERT INTO v1510_opportunity_trajectory(
                    symbol,observation_date,observed_at,price,opportunity_score,
                    flow_score,flow_type,relative_volume,rvol_3d_average,
                    high_volume_days_5d,close_location_pct,return_5d_pct,breakout_20d
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(symbol,observation_date) DO UPDATE SET
                    observed_at=excluded.observed_at,
                    price=excluded.price,
                    opportunity_score=excluded.opportunity_score,
                    flow_score=excluded.flow_score,
                    flow_type=excluded.flow_type,
                    relative_volume=excluded.relative_volume,
                    rvol_3d_average=excluded.rvol_3d_average,
                    high_volume_days_5d=excluded.high_volume_days_5d,
                    close_location_pct=excluded.close_location_pct,
                    return_5d_pct=excluded.return_5d_pct,
                    breakout_20d=excluded.breakout_20d
            """, vals)
            db.commit()

    def recent(self, symbol, days=10):
        with self._db() as db:
            rows = db.execute("""
                SELECT * FROM v1510_opportunity_trajectory
                WHERE symbol=? ORDER BY observation_date DESC LIMIT ?
            """, (_u(symbol), int(days))).fetchall()
        return [dict(r) for r in reversed(rows)]


def _trajectory_summary(rows, candidate):
    c = candidate or {}
    strong_days = 0
    breakout_days = 0
    prices = []
    for r in rows:
        fs = _f(r.get("flow_score"))
        rv = _f(r.get("relative_volume"))
        hd = int(_f(r.get("high_volume_days_5d"), 0) or 0)
        if (fs is not None and fs >= 65) and ((rv is not None and rv >= 1.3) or hd >= 2):
            strong_days += 1
        if int(r.get("breakout_20d") or 0):
            breakout_days += 1
        p = _f(r.get("price"))
        if p is not None:
            prices.append(p)

    retained = None
    if len(prices) >= 2 and prices[0] > 0:
        retained = (prices[-1] / prices[0] - 1) * 100.0

    scanner_high_days = int(_f(c.get("high_volume_days_5d"), 0) or 0)
    rvol3 = _f(c.get("rvol_3d_average"))
    persistence = (
        strong_days >= 2
        or scanner_high_days >= 2
        or (rvol3 is not None and rvol3 >= 1.5)
    )
    return {
        "distinct_days": len(rows),
        "strong_observation_days": strong_days,
        "breakout_observation_days": breakout_days,
        "price_change_since_first_observation_pct": round(retained, 2) if retained is not None else None,
        "scanner_high_volume_days_5d": scanner_high_days,
        "scanner_rvol_3d_average": rvol3,
        "persistent": bool(persistence),
    }


def _candidate_is_monitor_worthy(candidate, flow_label, trajectory, capital_level):
    c = candidate or {}
    opportunity = _f(c.get("opportunity_score"))
    dollar_volume = _f(c.get("current_dollar_volume"), _f(c.get("dollar_volume")))
    rvol = _f(c.get("relative_volume"))
    flow_score = _f(c.get("flow_score"))
    close_loc = _f(c.get("close_location_pct"))
    high_days = int(_f(c.get("high_volume_days_5d"), 0) or 0)

    if _u(capital_level) == "HIGH":
        return False

    quality = 0
    if opportunity is not None and opportunity >= 65:
        quality += 1
    if flow_score is not None and flow_score >= 70:
        quality += 2
    elif flow_score is not None and flow_score >= 60:
        quality += 1
    if rvol is not None and rvol >= 1.5:
        quality += 1
    if high_days >= 2:
        quality += 1
    if close_loc is not None and close_loc >= 55:
        quality += 1
    if dollar_volume is not None and dollar_volume >= 5_000_000:
        quality += 1
    if _b(c.get("breakout_20d")):
        quality += 1
    if trajectory.get("persistent"):
        quality += 1

    required = 7 if _u(capital_level) == "MODERATE" else 6
    return flow_label in {"STRONG", "CONSTRUCTIVE"} and quality >= required


def _fingerprint(intel):
    payload = {
        "stage": intel.stage,
        "phase": intel.phase,
        "setup_state": intel.setup_state,
        "ready": bool(intel.ready),
        "setup_type": intel.setup_type,
        "flow": asdict(intel.flow),
        "catalyst": asdict(intel.catalyst),
        "capital_risk": asdict(intel.capital_risk),
        "monitoring_signal": intel.monitoring_signal,
        "evidence_score": intel.evidence_score,
    }
    return sha256(json.dumps(payload, sort_keys=True, default=str, separators=(",", ":")).encode()).hexdigest()[:20]


def analyze(symbol, candidate, report, decision):
    candidate = candidate or {}
    report = report or {}
    decision = decision or {}

    intel = _base_analyze(symbol, candidate, report, decision)

    try:
        store = OpportunityTrajectoryStore()
        store.record(symbol, candidate)
        trajectory = _trajectory_summary(store.recent(symbol), candidate)
    except Exception:
        trajectory = _trajectory_summary([], candidate)

    base_insufficient = (
        _u(getattr(intel, "phase", "")) == "INSUFFICIENT_DATA"
        or _u(getattr(getattr(intel, "flow", None), "label", "")) == "INSUFFICIENT_DATA"
    )
    if not base_insufficient:
        return intel

    flow_label = _scanner_flow_label(candidate)
    phase = _scanner_phase(candidate, flow_label)

    # V15.10.1: refine only the research-monitoring capital-risk overlay
    # using structured SEC/event evidence. Production V11 risk and final
    # PAPER eligibility remain sovereign.
    structured_cap = evaluate_structured_capital_risk(
        report, candidate, getattr(intel, "catalyst", None)
    )

    raw = (report or {}).get("raw") or {}
    production = raw.get("production_result") or {}
    has_structured_capital_evidence = bool(
        isinstance(production.get("deep_sec"), dict)
        or isinstance(production.get("event_intelligence"), dict)
    )

    # V15.10.1b safety merge:
    # - If structured SEC/event evidence is present, use the structured refinement.
    # - If structured evidence is absent, preserve the base V15.5 capital-risk result.
    if has_structured_capital_evidence:
        intel.capital_risk.level = structured_cap.level
        intel.capital_risk.reasons = list(structured_cap.reasons)

    capital_level = _u(getattr(intel.capital_risk, "level", "UNKNOWN"))
    catalyst_strength = _u(getattr(getattr(intel, "catalyst", None), "strength", "NONE"))

    # V15.10.2 state reconciliation:
    # In the base INSUFFICIENT_DATA path, REVIEW can only have come from the
    # old HIGH capital-risk overlay (distribution risk cannot exist without bars).
    # If structured evidence refines that risk below HIGH, clear only that stale
    # REVIEW state. DATA_ISSUE / PROTECT_PROFIT / URGENT_REVIEW are untouched.
    if (
        has_structured_capital_evidence
        and capital_level != "HIGH"
        and _u(getattr(intel, "monitoring_signal", "")) == "REVIEW"
    ):
        intel.monitoring_signal = "CONTINUE"

    flow = intel.flow
    flow.rvol_20 = _f(candidate.get("relative_volume"))
    flow.dollar_volume = _f(candidate.get("current_dollar_volume"), _f(candidate.get("dollar_volume")))
    flow.persistence_5 = int(_f(candidate.get("high_volume_days_5d"), 0) or 0)
    flow.up_down_volume_ratio_5 = _f(candidate.get("up_down_volume_ratio_20d"))
    flow.atr_pct = _f(candidate.get("atr_pct"))
    flow.one_day_pct = _f(candidate.get("daily_change_pct"), _f(candidate.get("return_1d_pct")))
    flow.gap_pct = _f(candidate.get("gap_pct"))
    close_loc = _f(candidate.get("close_location_pct"))
    flow.close_location = close_loc / 100.0 if close_loc is not None else None
    flow.distance_sma20_pct = _f(candidate.get("distance_ema20_pct"))
    flow.label = flow_label

    setup_type = _setup_type(candidate, phase, flow_label, catalyst_strength)
    monitor = _candidate_is_monitor_worthy(candidate, flow_label, trajectory, capital_level)

    if monitor:
        intel.stage = "MONITOR"
        intel.phase = phase
        intel.setup_type = setup_type

        extras = []
        if candidate.get("flow_score") is not None:
            extras.append(f"Scanner flow score: {candidate.get('flow_score')}.")
        if candidate.get("relative_volume") is not None:
            extras.append(f"Scanner relative volume: {candidate.get('relative_volume')}x.")
        if candidate.get("high_volume_days_5d") is not None:
            extras.append(f"Scanner high-volume persistence: {candidate.get('high_volume_days_5d')}/5 sessions.")
        if candidate.get("close_location_pct") is not None:
            extras.append(f"Latest scanner close location: {candidate.get('close_location_pct')}% of session range.")
        if candidate.get("breakout_20d") is not None:
            extras.append(f"20-day breakout flag: {'YES' if _b(candidate.get('breakout_20d')) else 'NO'}.")

        existing = [
            x for x in (intel.observed_facts or [])
            if not str(x).startswith("Elevated positive-volume persistence:")
        ]
        for x in extras:
            if x not in existing:
                existing.append(x)
        intel.observed_facts = existing[:8]
        if structured_cap.evidence:
            existing_cap = list(intel.observed_facts or [])
            for msg in structured_cap.evidence[:2]:
                line = f"Capital-risk context: {msg}"
                if line not in existing_cap:
                    existing_cap.append(line)
            intel.observed_facts = existing_cap[:10]

        if has_structured_capital_evidence:
            stale_capital_phrases = {
                "Potential shelf/ATM financing overhang detected.",
                "Going-concern language detected.",
            }
            intel.contradicting_evidence = [
                x for x in (intel.contradicting_evidence or [])
                if str(x) not in stale_capital_phrases
            ]
            for reason in structured_cap.reasons:
                if reason not in intel.contradicting_evidence:
                    intel.contradicting_evidence.append(reason)
            intel.contradicting_evidence = intel.contradicting_evidence[:8]

            intel.next_conditions = [
                x for x in (intel.next_conditions or [])
                if str(x) != "Do not upgrade without resolving capital-structure/financing risk."
            ]
            if (
                capital_level == "MODERATE"
                and any(
                    "registration" in str(x).lower() or "atm" in str(x).lower()
                    for x in structured_cap.reasons
                )
            ):
                msg = (
                    "Continue monitoring registration/ATM-capacity risk and confirm "
                    "whether any actual issuance or active financing occurs."
                )
                if msg not in intel.next_conditions:
                    intel.next_conditions.append(msg)

        intel.interpretation = [
            f"Baby promotes this symbol to MONITOR because scanner evidence is {flow_label} and persistent enough for continued research.",
            f"Research phase fallback: {phase}.",
            f"Setup family: {setup_type}.",
            "This promotion is research monitoring only; it does not make the deterministic PAPER setup eligible.",
        ]
        scanner_score = _f(candidate.get("opportunity_score"))
        base_score = int(getattr(intel, "evidence_score", 0) or 0)
        scanner_component = int(round(scanner_score)) if scanner_score is not None else 0
        intel.evidence_score = max(base_score, min(85, scanner_component))
        nexts = list(intel.next_conditions or [])
        nexts.insert(0, "Continue monitoring for retained gains, repeated volume participation, and improving deterministic setup conditions.")
        intel.next_conditions = list(dict.fromkeys(nexts))[:6]
    else:
        intel.phase = phase if flow_label != "WEAK" else intel.phase
        if flow_label != "WEAK":
            intel.setup_type = setup_type
        existing = list(intel.observed_facts or [])
        if candidate.get("flow_score") is not None:
            msg = f"Scanner flow score: {candidate.get('flow_score')}."
            if msg not in existing:
                existing.append(msg)
        intel.observed_facts = existing[:8]

    # The bridge intentionally never changes base ready/setup_state.
    # Quantity remains USER_SELECTED and execution authority remains NONE.
    intel.fingerprint = _fingerprint(intel)
    return intel
