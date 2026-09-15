from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone, date
import math, re
from investor.sec_event_context import SECEventContextClassifier

@dataclass
class EventSignal:
    event_type: str
    title: str
    source: str
    event_date: str
    direction: str = "neutral"          # positive / negative / neutral / mixed / unknown
    materiality: str = "normal"         # low / normal / high / critical
    confidence: float = 0.0             # 0..1
    age_days: int | None = None
    freshness: float = 0.0              # 0..1
    effective_confidence: float = 0.0   # confidence * freshness
    filing_form: str | None = None
    url: str | None = None
    evidence_class: str = "secondary"   # primary / secondary
    notes: list[str] = field(default_factory=list)

@dataclass
class EventIntelligenceReport:
    score: float = 50.0
    confidence: float = 0.0
    coverage: float = 0.0
    positive_pressure: float = 0.0
    negative_pressure: float = 0.0
    high_materiality_count: int = 0
    active_event_count: int = 0
    primary_event_count: int = 0
    secondary_event_count: int = 0
    events: list[EventSignal] = field(default_factory=list)
    positives: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    unknowns: list[str] = field(default_factory=list)

class EventIntelligenceEngine:
    """
    Deterministic V3.9 event layer.

    Critical rule: filing FORM is evidence that a filing exists, not proof that
    securities were issued, an insider bought/sold, or an 8-K was bullish/bearish.
    Those require document/transaction-level evidence.
    """

    FORM_RULES = {
        "10-K": ("periodic_report","neutral","high",.98,180),
        "10-Q": ("periodic_report","neutral","high",.98,120),
        "20-F": ("periodic_report","neutral","high",.98,180),
        "8-K": ("current_report","unknown","high",.98,45),
        "6-K": ("current_report","unknown","high",.98,45),
        "S-1": ("registration","unknown","high",.98,120),
        "S-3": ("registration","unknown","high",.98,120),
        "F-1": ("registration","unknown","high",.98,120),
        "F-3": ("registration","unknown","high",.98,120),
        "424B3": ("prospectus","unknown","high",.98,90),
        "424B5": ("prospectus","unknown","high",.98,90),
        "4": ("insider_transaction_filing","unknown","normal",.98,45),
        "SC 13D": ("ownership_filing","unknown","high",.98,90),
        "SC 13G": ("ownership_filing","unknown","normal",.98,90),
        "DEF 14A": ("proxy","neutral","normal",.98,120),
    }

    NEWS_RULES = [
        (r"\b(raises?|raised) guidance\b","guidance_raise","positive","high"),
        (r"\b(cuts?|cut|lowers?|lowered) guidance\b","guidance_cut","negative","high"),
        (r"\b(beats?|beat) (estimates?|expectations?|consensus)\b","earnings_beat","positive","high"),
        (r"\b(misses?|missed) (estimates?|expectations?|consensus)\b","earnings_miss","negative","high"),
        (r"\b(fda|food and drug administration).{0,35}\b(approves?|approved|approval)\b","regulatory_approval","positive","critical"),
        (r"\b(fda|food and drug administration).{0,35}\b(rejects?|rejected|complete response letter)\b","regulatory_setback","negative","critical"),
        (r"\b(merger agreement|to acquire|acquisition agreement)\b","m_and_a","mixed","high"),
        (r"\b(bankruptcy|chapter 11)\b","bankruptcy","negative","critical"),
        (r"\b(delisting notice|to be delisted)\b","delisting","negative","critical"),
        (r"\b(registered direct offering|public offering|at-the-market offering)\b","offering_news","negative","high"),
        (r"\b(share repurchase|stock repurchase|buyback)\b","buyback_news","positive","high"),
        (r"\b(material contract|major contract|strategic partnership)\b","commercial_event","positive","high"),
    ]

    def __init__(self):
        self.sec_context_classifier = SECEventContextClassifier()

    def analyze(self, sec_analysis=None, news_items=None, deep_sec=None, now=None):
        now = now or datetime.now(timezone.utc)
        events=[]
        for f in getattr(sec_analysis,"recent_filings",[]) or []:
            rule=self.FORM_RULES.get(getattr(f,"form",""))
            if not rule: continue
            typ,direction,materiality,conf,half_life=rule
            dt=self._date(getattr(f,"filing_date",""))
            age=self._age(dt,now)
            fresh=self._decay(age,half_life)
            notes=[]
            form=getattr(f,"form","")
            if form in {"S-1","S-3","F-1","F-3","424B3","424B5"}:
                notes.append("Registration/prospectus filing does not by itself prove securities were issued or dilution occurred.")
            if form=="4":
                notes.append("Form 4 confirms an insider transaction filing exists; transaction direction requires transaction-level parsing.")
            if form in {"8-K","6-K"}:
                notes.append("Current-report filing is material-event metadata; direction requires filing-content classification.")
            events.append(EventSignal(
                event_type=typ,title=f"{form} filing",source="SEC EDGAR",event_date=str(getattr(f,"filing_date","")),
                direction=direction,materiality=materiality,confidence=conf,age_days=age,freshness=fresh,
                effective_confidence=round(conf*fresh,4),filing_form=form,url=getattr(f,"filing_url",None),
                evidence_class="primary",notes=notes,
            ))

        for item in (news_items or [])[:40]:
            content=item.get("content",item) if isinstance(item,dict) else {}
            title=(content.get("title") or (item.get("title") if isinstance(item,dict) else "") or "").strip()
            if not title: continue
            match_rule=None
            for pattern,typ,direction,materiality in self.NEWS_RULES:
                if re.search(pattern,title,re.I):
                    match_rule=(typ,direction,materiality);break
            if not match_rule: continue
            typ,direction,materiality=match_rule
            raw=content.get("pubDate") or (item.get("providerPublishTime") if isinstance(item,dict) else None)
            dt=self._date(raw); age=self._age(dt,now); fresh=self._decay(age,30)
            provider=(content.get("provider") or {})
            source=provider.get("displayName") if isinstance(provider,dict) else None
            source=source or (item.get("publisher") if isinstance(item,dict) else None) or "secondary news"
            url=self._url(content,item)
            conf=.62
            events.append(EventSignal(
                event_type=typ,title=title,source=source,event_date=dt.isoformat() if dt else "",
                direction=direction,materiality=materiality,confidence=conf,age_days=age,freshness=fresh,
                effective_confidence=round(conf*fresh,4),url=url,evidence_class="secondary",
                notes=["Headline classification only; verify material claims against primary company/regulatory evidence."],
            ))

        # Deep SEC findings may provide direction for financing/distress, but still
        # distinguish registration language from completed issuance.
        for finding in getattr(deep_sec,"all_findings",[]) or []:
            category=getattr(finding,"category","")
            if category not in {"going_concern","reverse_split","convertible_debt","offering","warrant"}: continue
            dt=self._date(getattr(finding,"filing_date",""));age=self._age(dt,now);fresh=self._decay(age,90)
            if category=="going_concern":
                direction,mat,conf="negative","critical",.94
                stage="ACTIVE_RISK"
                notes=["Going-concern language is primary distress evidence."]
            else:
                classified=self.sec_context_classifier.classify(finding)
                stage=classified.stage
                direction=classified.direction
                conf=classified.confidence
                mat="high" if category in {"offering","warrant","convertible_debt","reverse_split"} else "normal"
                notes=list(classified.reasons)

            # Keep the observation, but encode semantic stage in the event type.
            # Only announced/active/completed financing can become directional.
            events.append(EventSignal(
                event_type=f"sec_{category}:{stage}",title=getattr(finding,"phrase",category),source="SEC filing content",
                event_date=str(getattr(finding,"filing_date","")),direction=direction,materiality=mat,
                confidence=conf,age_days=age,freshness=fresh,effective_confidence=round(conf*fresh,4),
                filing_form=getattr(finding,"filing_form",None),url=getattr(finding,"filing_url",None),
                evidence_class="primary",notes=notes,
            ))

        events=self._dedupe(events)
        pos=neg=0.0
        for e in events:
            weight={"low":.5,"normal":1.0,"high":1.7,"critical":2.5}.get(e.materiality,1.0)
            pressure=weight*e.effective_confidence
            if e.direction=="positive": pos+=pressure
            elif e.direction=="negative": neg+=pressure

        # Unknown/neutral events affect awareness/coverage, never direction.
        net=pos-neg
        score=50 + 35*math.tanh(net/3.0)
        active=[e for e in events if e.freshness>=.20]
        directional=[e for e in active if e.direction in {"positive","negative","mixed"}]
        primary=[e for e in active if e.evidence_class=="primary"]
        confidence=(sum(e.effective_confidence for e in active)/len(active)*100) if active else 0.
        coverage=min(100., 25. + (25. if primary else 0.) + (25. if directional else 0.) + min(25.,len(active)*2.5)) if events else 0.

        positives=[e.title for e in active if e.direction=="positive"][:8]
        risks=[e.title for e in active if e.direction=="negative"][:8]
        unknowns=[]
        if not events: unknowns.append("no_classified_events")
        if not primary: unknowns.append("no_active_primary_events")
        if not directional: unknowns.append("no_verified_directional_events")

        return EventIntelligenceReport(
            score=round(max(0,min(100,score)),2),confidence=round(confidence,2),coverage=round(coverage,2),
            positive_pressure=round(pos,3),negative_pressure=round(neg,3),
            high_materiality_count=sum(e.materiality in {"high","critical"} for e in active),
            active_event_count=len(active),primary_event_count=len(primary),
            secondary_event_count=sum(e.evidence_class=="secondary" for e in active),
            events=sorted(events,key=lambda e:(e.age_days if e.age_days is not None else 99999,e.evidence_class!="primary")),
            positives=positives,risks=risks,unknowns=unknowns,
        )

    @staticmethod
    def _dedupe(events):
        out=[];seen=set()
        for e in events:
            key=(e.event_type,e.event_date,e.filing_form,e.title.lower()[:120])
            if key in seen: continue
            seen.add(key);out.append(e)
        return out
    @staticmethod
    def _decay(age,half_life):
        if age is None:return .35
        if age<0:return .25
        return round(0.5**(age/max(1,half_life)),4)
    @staticmethod
    def _age(dt,now):
        if not dt:return None
        d=dt.date() if isinstance(dt,datetime) else dt
        return (now.date()-d).days
    @staticmethod
    def _date(v):
        if v is None:return None
        if isinstance(v,(int,float)):
            try:return datetime.fromtimestamp(v,tz=timezone.utc).date()
            except Exception:return None
        if isinstance(v,datetime):return v.date()
        if isinstance(v,date):return v
        text=str(v).strip()
        if not text:return None
        try:return datetime.fromisoformat(text.replace("Z","+00:00")).date()
        except Exception:
            try:return datetime.strptime(text[:10],"%Y-%m-%d").date()
            except Exception:return None
    @staticmethod
    def _url(content,item):
        for key in ("canonicalUrl","clickThroughUrl"):
            obj=content.get(key,{}) if isinstance(content,dict) else {}
            if isinstance(obj,dict) and obj.get("url"):return obj["url"]
        return item.get("link") if isinstance(item,dict) else None
