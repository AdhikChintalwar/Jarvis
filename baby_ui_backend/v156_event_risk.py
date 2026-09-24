from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from math import isfinite
from urllib.parse import urlparse


def _f(v, d=None):
    try:
        x = float(v)
        return x if isfinite(x) else d
    except Exception:
        return d


def _u(v):
    return str(v or "").strip().upper()


def _s(v):
    return str(v or "").strip()


def _dt(v):
    if v is None or v == "":
        return None
    text = str(v).strip()
    if not text:
        return None
    # Date-only events are interpreted as known by end-of-day in daily replay.
    if len(text) == 10 and text[4] == "-" and text[7] == "-":
        text = text + "T23:59:59+00:00"
    try:
        d = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except Exception:
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc)


def _domain(item):
    raw = _s(item.get("domain") or item.get("url") or item.get("link") or item.get("source_url"))
    if not raw:
        return ""
    if "://" not in raw and "." in raw and "/" not in raw:
        return raw.lower()
    try:
        return (urlparse(raw).netloc or "").lower().removeprefix("www.")
    except Exception:
        return raw.lower()


def source_tier(item):
    """Evidence hierarchy.

    A_PRIMARY_OFFICIAL:
      SEC, FDA, exchange/regulator, or explicitly tagged official/company-primary.
    B_COMPANY_DISTRIBUTION:
      press-release distribution services carrying company releases.
    B_HIGH_QUALITY_SECONDARY:
      Reuters/Bloomberg/AP/FT/WSJ.
    C_MARKET_NEWS:
      market-focused media.
    D_OTHER:
      everything else.

    We deliberately do NOT treat BusinessWire/GlobeNewswire/PRNewswire as identical
    to an SEC filing or regulator source.
    """
    domain = _domain(item)
    source = _s(item.get("source")).lower()
    source_type = _s(item.get("source_type") or item.get("evidence_type")).lower()
    explicit_primary = item.get("is_primary") is True or source_type in {
        "primary", "official", "company_ir", "regulator", "exchange", "sec_filing"
    }

    if explicit_primary:
        return "A_PRIMARY_OFFICIAL"

    if any(x in domain for x in (
        "sec.gov", "fda.gov", "nasdaqtrader.com", "nyse.com",
        "investor.", "investors."
    )):
        return "A_PRIMARY_OFFICIAL"

    if any(x in domain for x in (
        "businesswire.com", "globenewswire.com", "prnewswire.com", "accesswire.com"
    )):
        return "B_COMPANY_DISTRIBUTION"

    if any(x in source or x in domain for x in (
        "reuters", "bloomberg", "associated press", "apnews", "ft.com",
        "financial times", "wsj.com", "wall street journal"
    )):
        return "B_HIGH_QUALITY_SECONDARY"

    if any(x in source or x in domain for x in (
        "benzinga", "marketwatch", "seekingalpha", "thestreet"
    )):
        return "C_MARKET_NEWS"

    return "D_OTHER"


EVENT_PATTERNS = [
    ("MERGER", ("definitive agreement", "merger", "tender offer", "acquire", "acquisition")),
    ("FDA_REGULATORY", ("fda", "clinical trial", "clearance", "approval", "complete response letter", "crl")),
    ("EARNINGS", ("earnings", "quarterly results", "financial results", "revenue", "eps", "guidance")),
    ("CONTRACT", ("contract", "purchase order", "award", "customer agreement")),
    ("BUYBACK", ("share repurchase", "repurchase program", "buyback")),
    ("FINANCING_OFFERING", ("public offering", "registered direct", "private placement", "follow-on offering", "share offering")),
    ("ATM_SHELF", ("at-the-market", "atm program", "shelf registration", "form s-3", "s-3 registration")),
    ("WARRANT_CONVERTIBLE", ("warrant", "convertible note", "convertible debt", "convertible preferred")),
    ("REVERSE_SPLIT", ("reverse stock split", "reverse split")),
    ("NASDAQ_COMPLIANCE", ("minimum bid price", "nasdaq deficiency", "listing deficiency", "compliance period")),
    ("TRADING_HALT", ("trading halt", "halted trading", "t1 halt", "t12 halt")),
    ("GOING_CONCERN", ("going concern", "substantial doubt")),
    ("PARTNERSHIP", ("partnership", "strategic relationship", "collaboration")),
    ("INDEX_EVENT", ("russell 2000", "russell 3000", "index inclusion", "reconstitution", "index deletion")),
    ("MANAGEMENT", ("chief executive", " ceo ", "chief financial", " cfo ", "resigned", "appointed")),
    ("LEGAL", ("lawsuit", "investigation", "subpoena", "fraud", "class action")),
    ("DILUTION_SHARE_ISSUANCE", ("share issuance", "issued shares", "common shares issued", "equity issuance")),
]


def classify_event(item):
    explicit = _u(item.get("event_type"))
    if explicit and explicit not in {"OTHER", "UNKNOWN", "NONE"}:
        return explicit

    text = " " + " ".join(
        _s(item.get(k))
        for k in ("headline", "title", "summary", "description", "form", "filing_form")
    ).lower() + " "

    for name, terms in EVENT_PATTERNS:
        if any(term in text for term in terms):
            return name
    return "OTHER" if text.strip() else "NONE"


@dataclass
class EventEvidence:
    event_type: str
    headline: str
    source: str
    source_tier: str
    published_at: str | None
    form: str | None = None
    url: str | None = None
    age_days: float | None = None


@dataclass
class EventRiskAssessment:
    catalyst_regime: str = "NONE"
    catalyst_strength: str = "NONE"
    catalyst_source_tier: str = "NONE"
    catalyst_headline: str | None = None
    catalyst_published_at: str | None = None
    catalyst_causality: str = "NOT_ESTABLISHED"

    structural_risk_level: str = "LOW"
    structural_risk_score: int = 0
    structural_risk_reasons: list[str] | None = None

    events_seen: int = 0
    primary_events_seen: int = 0
    latest_event_time: str | None = None
    conflicting_evidence: list[str] | None = None

    def as_dict(self):
        return asdict(self)


RISK_WEIGHTS = {
    "FINANCING_OFFERING": 3,
    "ATM_SHELF": 2,
    "WARRANT_CONVERTIBLE": 2,
    "REVERSE_SPLIT": 2,
    "NASDAQ_COMPLIANCE": 2,
    "TRADING_HALT": 3,
    "GOING_CONCERN": 3,
    "DILUTION_SHARE_ISSUANCE": 2,
    "LEGAL": 1,
}

CATALYST_PRIORITY = {
    "MERGER": 10,
    "FDA_REGULATORY": 9,
    "EARNINGS": 8,
    "CONTRACT": 7,
    "BUYBACK": 6,
    "FINANCING_OFFERING": 6,
    "ATM_SHELF": 5,
    "PARTNERSHIP": 5,
    "INDEX_EVENT": 5,
    "MANAGEMENT": 4,
    "LEGAL": 4,
    "REVERSE_SPLIT": 3,
    "NASDAQ_COMPLIANCE": 3,
    "TRADING_HALT": 3,
    "WARRANT_CONVERTIBLE": 3,
    "DILUTION_SHARE_ISSUANCE": 3,
    "GOING_CONCERN": 2,
    "OTHER": 1,
    "NONE": 0,
}

TIER_SCORE = {
    "A_PRIMARY_OFFICIAL": 4,
    "B_HIGH_QUALITY_SECONDARY": 3,
    "B_COMPANY_DISTRIBUTION": 3,
    "C_MARKET_NEWS": 2,
    "D_OTHER": 1,
    "NONE": 0,
}


def _collect_rows(candidate, report, decision):
    rows = []
    for src in (
        (report or {}).get("events"),
        (report or {}).get("news"),
        (report or {}).get("filings"),
        (candidate or {}).get("events"),
        (candidate or {}).get("news"),
        (candidate or {}).get("filings"),
        (decision or {}).get("events"),
        ((decision or {}).get("research_decision") or {}).get("events"),
        (((decision or {}).get("proposal") or {}).get("payload") or {}).get("events"),
    ):
        if isinstance(src, list):
            rows.extend(x for x in src if isinstance(x, dict))

    # Deduplicate conservatively.
    seen = set()
    out = []
    for x in rows:
        key = (
            _s(x.get("headline") or x.get("title")).lower(),
            _s(x.get("published_at") or x.get("event_time") or x.get("date")),
            _s(x.get("form") or x.get("filing_form")).upper(),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(x)
    return out


def assess_events(symbol, candidate=None, report=None, decision=None, as_of=None):
    candidate = candidate or {}
    report = report or {}
    decision = decision or {}

    asof = _dt(as_of)
    now = asof or datetime.now(timezone.utc)

    evidence = []
    for item in _collect_rows(candidate, report, decision):
        dt = _dt(
            item.get("published_at")
            or item.get("event_time")
            or item.get("timestamp")
            or item.get("created_at")
            or item.get("date")
        )
        # Strict point-in-time filter.
        if asof is not None and dt is not None and dt > asof:
            continue

        ev = classify_event(item)
        tier = source_tier(item)
        age = None
        if dt is not None:
            age = max(0.0, (now - dt).total_seconds() / 86400.0)

        evidence.append(
            EventEvidence(
                event_type=ev,
                headline=_s(item.get("headline") or item.get("title") or item.get("description")),
                source=_s(item.get("source") or item.get("domain") or "UNKNOWN"),
                source_tier=tier,
                published_at=dt.isoformat() if dt else None,
                form=_s(item.get("form") or item.get("filing_form")) or None,
                url=_s(item.get("url") or item.get("link")) or None,
                age_days=round(age, 3) if age is not None else None,
            )
        )

    if not evidence:
        return EventRiskAssessment(
            structural_risk_reasons=["No structural-risk event is established in the current point-in-time inputs."],
            conflicting_evidence=[],
        )

    # Structural risk: only count reasonably recent risk events, with longer memory
    # for structural actions that can matter for months.
    risk_score = 0
    risk_reasons = []
    for e in evidence:
        w = RISK_WEIGHTS.get(e.event_type, 0)
        if not w:
            continue

        max_age = 365 if e.event_type in {
            "REVERSE_SPLIT", "ATM_SHELF", "WARRANT_CONVERTIBLE",
            "NASDAQ_COMPLIANCE", "GOING_CONCERN"
        } else 180

        if e.age_days is None or e.age_days <= max_age:
            # Primary/official evidence gets full weight. Weak-source-only evidence
            # is capped so an aggregator headline cannot create CRITICAL risk alone.
            effective = w if e.source_tier in {
                "A_PRIMARY_OFFICIAL", "B_HIGH_QUALITY_SECONDARY", "B_COMPANY_DISTRIBUTION"
            } else max(1, w - 1)
            risk_score += effective
            label = e.headline or e.event_type
            risk_reasons.append(f"{e.event_type}: {label} [{e.source_tier}]")

    if risk_score >= 7:
        risk_level = "CRITICAL"
    elif risk_score >= 4:
        risk_level = "HIGH"
    elif risk_score >= 2:
        risk_level = "MODERATE"
    else:
        risk_level = "LOW"

    # Pick the strongest catalyst using type, evidence tier, and freshness.
    ranked = []
    for e in evidence:
        fresh = 3 if e.age_days is not None and e.age_days <= 3 else 2 if e.age_days is not None and e.age_days <= 14 else 1
        score = CATALYST_PRIORITY.get(e.event_type, 0) * 10 + TIER_SCORE.get(e.source_tier, 0) * 3 + fresh
        ranked.append((score, e))

    _, best = max(ranked, key=lambda z: z[0])

    if best.event_type == "MERGER":
        catalyst_regime = "EVENT_DRIVEN_MERGER"
    elif best.event_type == "FDA_REGULATORY":
        catalyst_regime = "EVENT_DRIVEN_FDA_REGULATORY"
    elif best.event_type == "EARNINGS":
        catalyst_regime = "EVENT_DRIVEN_EARNINGS"
    elif best.event_type == "FINANCING_OFFERING":
        catalyst_regime = "EVENT_DRIVEN_FINANCING"
    elif best.event_type == "ATM_SHELF":
        catalyst_regime = "EVENT_DRIVEN_FINANCING_OVERHANG"
    elif best.event_type == "CONTRACT":
        catalyst_regime = "EVENT_DRIVEN_CONTRACT"
    elif best.event_type == "BUYBACK":
        catalyst_regime = "EVENT_DRIVEN_BUYBACK"
    elif best.event_type == "PARTNERSHIP":
        catalyst_regime = "EVENT_DRIVEN_PARTNERSHIP"
    elif best.event_type == "INDEX_EVENT":
        catalyst_regime = "EVENT_DRIVEN_INDEX"
    elif best.event_type == "MANAGEMENT":
        catalyst_regime = "EVENT_DRIVEN_MANAGEMENT"
    elif best.event_type == "LEGAL":
        catalyst_regime = "EVENT_DRIVEN_LEGAL"
    elif best.event_type in {"REVERSE_SPLIT","NASDAQ_COMPLIANCE","TRADING_HALT","GOING_CONCERN","WARRANT_CONVERTIBLE","DILUTION_SHARE_ISSUANCE"}:
        catalyst_regime = "STRUCTURAL_EVENT"
    else:
        catalyst_regime = "OTHER_EVENT"

    if best.source_tier == "A_PRIMARY_OFFICIAL" and best.event_type in {
        "MERGER","FDA_REGULATORY","EARNINGS","CONTRACT","FINANCING_OFFERING","BUYBACK"
    }:
        strength = "HIGH"
    elif best.source_tier in {
        "A_PRIMARY_OFFICIAL","B_HIGH_QUALITY_SECONDARY","B_COMPANY_DISTRIBUTION"
    }:
        strength = "MEDIUM"
    else:
        strength = "LOW"

    conflicts = []
    if catalyst_regime in {
        "EVENT_DRIVEN_CONTRACT","EVENT_DRIVEN_BUYBACK","EVENT_DRIVEN_PARTNERSHIP",
        "EVENT_DRIVEN_FDA_REGULATORY","EVENT_DRIVEN_EARNINGS"
    } and risk_level in {"HIGH","CRITICAL"}:
        conflicts.append(
            f"Potentially positive catalyst coexists with {risk_level} structural risk; do not treat the catalyst as sufficient by itself."
        )

    latest = max(
        (e.published_at for e in evidence if e.published_at),
        default=None
    )

    return EventRiskAssessment(
        catalyst_regime=catalyst_regime,
        catalyst_strength=strength,
        catalyst_source_tier=best.source_tier,
        catalyst_headline=best.headline or None,
        catalyst_published_at=best.published_at,
        catalyst_causality="NOT_ESTABLISHED",
        structural_risk_level=risk_level,
        structural_risk_score=risk_score,
        structural_risk_reasons=risk_reasons or [
            "No material structural-risk event is established in the current point-in-time inputs."
        ],
        events_seen=len(evidence),
        primary_events_seen=sum(1 for e in evidence if e.source_tier == "A_PRIMARY_OFFICIAL"),
        latest_event_time=latest,
        conflicting_evidence=conflicts,
    )
