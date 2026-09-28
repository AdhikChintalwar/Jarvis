from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class StructuredCapitalRisk:
    level: str
    reasons: list[str]
    evidence: list[str]
    status: str = "STRUCTURED"


def _u(v):
    return str(v or "").strip().upper()


def _text(v):
    return str(v or "").strip()


def _all_text(x):
    if isinstance(x, dict):
        return " ".join(_all_text(v) for v in x.values())
    if isinstance(x, list):
        return " ".join(_all_text(v) for v in x)
    return _text(x)


def _event_rows(report):
    raw = (report or {}).get("raw") or {}
    prod = raw.get("production_result") or {}
    ei = prod.get("event_intelligence") or {}
    rows = ei.get("events") or []
    return [x for x in rows if isinstance(x, dict)]


def _deep_sec(report):
    raw = (report or {}).get("raw") or {}
    prod = raw.get("production_result") or {}
    sec = prod.get("deep_sec") or {}
    return sec if isinstance(sec, dict) else {}


def _parse_dt(v):
    if not v:
        return None
    try:
        s = str(v).replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _event_dt(e):
    for k in ("published_at", "filed_at", "filing_date", "created_at", "accepted_at", "date", "timestamp"):
        dt = _parse_dt(e.get(k))
        if dt:
            return dt
    return None


def _recent(e, days=120):
    dt = _event_dt(e)
    if not dt:
        return False
    return (datetime.now(timezone.utc) - dt).total_seconds() <= days * 86400


RESOLVED_GOING_CONCERN = (
    "removed the substantial doubt",
    "substantial doubt was alleviated",
    "substantial doubt has been alleviated",
    "no longer substantial doubt",
    "removed substantial doubt",
)

ACTIVE_GOING_CONCERN = (
    "substantial doubt about",
    "substantial doubt exists",
    "raises substantial doubt",
    "ability to continue as a going concern",
)

REGISTRATION_ONLY_TERMS = (
    "registration",
    "prospectus",
    "s-3",
    "s-1",
    "424b",
    "rule 415",
)

ACTIVE_FINANCING_TERMS = (
    "entered into an at-the-market",
    "entered into a sales agreement",
    "commenced an offering",
    "priced an offering",
    "pricing of",
    "sold shares",
    "issued shares",
    "net proceeds",
    "gross proceeds",
    "closed the offering",
    "closing of the offering",
    "completed the offering",
    "private placement",
    "registered direct offering",
)

COMPLETION_TERMS = (
    "completed",
    "closed",
    "closing",
    "net proceeds",
    "gross proceeds",
    "sold",
    "issued",
)


def evaluate_structured_capital_risk(report, candidate=None, catalyst=None):
    report = report or {}
    sec = _deep_sec(report)
    events = _event_rows(report)

    evidence = []
    reasons = []

    gc_flags = sec.get("going_concern_flags") or []
    gc_text = " ".join(_all_text(x).lower() for x in gc_flags if isinstance(x, dict))
    resolved_gc = any(t in gc_text for t in RESOLVED_GOING_CONCERN)

    active_gc = False
    if gc_text and not resolved_gc:
        active_gc = any(t in gc_text for t in ACTIVE_GOING_CONCERN)

    if resolved_gc:
        evidence.append("Prior going-concern doubt appears explicitly resolved/alleviated in current structured SEC context.")
        reasons.append("Historical going-concern risk noted, with explicit resolution language.")
    elif active_gc:
        evidence.append("Structured SEC evidence contains unresolved substantial-doubt / going-concern language.")
        reasons.append("Current unresolved going-concern risk detected.")

    offering_flags = sec.get("offering_flags") or []

    registration_events = []
    active_events = []
    completed_events = []

    for e in events:
        et = _u(e.get("event_type"))
        blob = _all_text(e).lower()
        notes = " ".join(str(x).lower() for x in (e.get("notes") or []))

        if (
            "REGISTRATION" in et
            or et == "PROSPECTUS"
            or "registration/prospectus" in notes
            or "does not by itself prove securities were issued" in notes
        ):
            registration_events.append(e)

        active_signal = any(t in blob for t in ACTIVE_FINANCING_TERMS)
        completed_signal = any(t in blob for t in COMPLETION_TERMS)

        registration_only = (
            any(t in blob for t in REGISTRATION_ONLY_TERMS)
            and not active_signal
            and not completed_signal
        )

        if completed_signal and _recent(e, 180):
            completed_events.append(e)
        elif active_signal and not registration_only and _recent(e, 120):
            active_events.append(e)

    has_registration_overhang = bool(registration_events) or bool(offering_flags)

    if active_events:
        evidence.append("Recent structured event evidence indicates an active financing/offering process.")
        reasons.append("Recent active financing/offering risk detected.")
    elif completed_events:
        evidence.append("Recent structured event evidence indicates a financing/offering completed.")
        reasons.append("Recent completed financing may affect supply/dilution context.")
    elif has_registration_overhang:
        evidence.append("Registration/prospectus or ATM-capacity language detected without structured evidence of completed issuance.")
        reasons.append("Registration/ATM capacity overhang detected; issuance is not established.")

    if active_gc:
        level = "HIGH"
    elif active_events:
        level = "MODERATE"
    elif completed_events or has_registration_overhang or resolved_gc:
        level = "MODERATE"
    else:
        level = "LOW"
        reasons = ["No major structured capital-structure red flag detected in current Baby inputs."]
        evidence = ["No current structured SEC/event evidence requiring a capital-risk overlay was identified."]

    return StructuredCapitalRisk(level, reasons, evidence)
