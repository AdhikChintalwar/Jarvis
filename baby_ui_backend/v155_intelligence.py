from __future__ import annotations
from dataclasses import dataclass,asdict
from datetime import datetime,timezone
from hashlib import sha256
from statistics import median
from math import isfinite
import json

def f(v,d=None):
    try:
        x=float(v); return x if isfinite(x) else d
    except Exception:return d

def upper(v): return str(v or '').strip().upper()
def iso_dt(v):
    try:return datetime.fromisoformat(str(v).replace('Z','+00:00'))
    except Exception:return None

def paper(decision): return (((decision or {}).get('proposal') or {}).get('payload') or {}).get('paper_proposal') or {}
def setup_state(decision):
    payload=((decision or {}).get('proposal') or {}).get('payload') or {}; p=payload.get('paper_proposal') or {}
    return upper(p.get('setup_status') or payload.get('setup_status') or p.get('status') or decision.get('status') or 'UNKNOWN')
def ready(decision):
    p=paper(decision); return bool(p.get('eligible')) and upper(p.get('status'))=='ELIGIBLE'

def bars_from(report,candidate,decision):
    for rows in [report.get('bars'),report.get('daily_bars'),report.get('history'),candidate.get('bars'),candidate.get('daily_bars'),((decision.get('research_decision') or {}).get('bars')),(((decision.get('proposal') or {}).get('payload') or {}).get('bars'))]:
        if isinstance(rows,list) and rows:
            out=[]
            for b in rows:
                if isinstance(b,dict) and f(b.get('close')) is not None and f(b.get('volume')) is not None: out.append(dict(b))
            if out:return out[-120:]
    return []

def atr(bars,n=14):
    if len(bars)<2:return None
    out=[]; prev=f(bars[0].get('close'))
    for b in bars[1:]:
        h,l,c=f(b.get('high')),f(b.get('low')),f(b.get('close'))
        if None not in (h,l,c,prev):out.append(max(h-l,abs(h-prev),abs(l-prev)))
        if c is not None:prev=c
    return sum(out[-n:])/min(n,len(out)) if out else None

def clv(b):
    h,l,c=f(b.get('high')),f(b.get('low')),f(b.get('close'))
    return 0.0 if None in (h,l,c) or h<=l else ((c-l)-(h-c))/(h-l)

def pct(a,b):
    a,b=f(a),f(b)
    return None if a is None or b in (None,0) else (a/b-1)*100

def sma(vals,n):
    vals=[f(x) for x in vals]
    vals=[x for x in vals if x is not None]
    return None if len(vals)<n else sum(vals[-n:])/n

@dataclass
class Flow:
    rvol_20:float|None=None
    dollar_volume:float|None=None
    persistence_5:int=0
    up_down_volume_ratio_5:float|None=None
    weighted_clv_5:float|None=None
    retention_20:float|None=None
    atr_pct:float|None=None
    one_day_pct:float|None=None
    gap_pct:float|None=None
    true_range_atr:float|None=None
    distance_sma5_pct:float|None=None
    distance_sma20_pct:float|None=None
    extension_from_20d_low_pct:float|None=None
    close_location:float|None=None
    position_gain_pct:float|None=None
    bar_pattern:str='NORMAL'
    label:str='INSUFFICIENT_DATA'

@dataclass
class Catalyst:
    event_type:str='NONE'; strength:str='NONE'; source_tier:str='NONE'; headline:str|None=None; source:str|None=None; published_at:str|None=None; causality:str='NOT_ESTABLISHED'

@dataclass
class CapitalRisk:
    level:str='LOW'; reasons:list[str]|None=None

@dataclass
class Intelligence:
    symbol:str
    stage:str
    phase:str
    setup_state:str
    ready:bool
    setup_type:str
    flow:Flow
    catalyst:Catalyst
    capital_risk:CapitalRisk
    observed_facts:list[str]
    interpretation:list[str]
    contradicting_evidence:list[str]
    next_conditions:list[str]
    monitoring_signal:str
    evidence_score:int
    fingerprint:str
    def as_dict(self):return asdict(self)

EVENTS=[('MERGER',('acquire','acquisition','merger','definitive agreement','tender offer')),('FINANCING',('offering','registered direct','private placement','at-the-market','convertible','warrant')),('BUYBACK',('repurchase','buyback')),('EARNINGS',('earnings','results','guidance','revenue','eps')),('CONTRACT',('contract','purchase order','award')),('FDA_REGULATORY',('fda','clinical trial','approval','clearance')),('INDEX_EVENT',('russell 2000','index inclusion','reconstitution')),('MANAGEMENT',('ceo','cfo','chief executive','resign','appointed')),('PARTNERSHIP',('partnership','strategic relationship','collaboration')),('LEGAL',('investigation','lawsuit','subpoena','fraud'))]

def event_type(headline):
    h=str(headline or '').lower()
    for name,terms in EVENTS:
        if any(t in h for t in terms):return name
    return 'OTHER' if h else 'NONE'

def source_tier(item):
    t=' '.join(str(item.get(k) or '') for k in ('source','url','link','domain')).lower()
    if any(x in t for x in ('sec.gov','investor.','businesswire.com','globenewswire.com','prnewswire.com','accesswire.com')):return 'A_PRIMARY'
    if any(x in t for x in ('reuters','bloomberg','associated press','wsj','financial times')):return 'B_HIGH_QUALITY_SECONDARY'
    if any(x in t for x in ('benzinga','marketwatch','seekingalpha','thestreet')):return 'C_MARKET_NEWS'
    return 'D_OTHER'

def news_rows(report,candidate,decision):
    rows=[]
    for src in (report.get('news'),report.get('recent_news'),candidate.get('news'),((decision.get('research_decision') or {}).get('news')),(((decision.get('proposal') or {}).get('payload') or {}).get('news'))):
        if isinstance(src,list):rows.extend(x for x in src if isinstance(x,dict))
    seen=set(); out=[]
    for x in rows:
        h=str(x.get('headline') or x.get('title') or '').strip()
        if h and h.lower() not in seen:seen.add(h.lower());out.append(x)
    return out[:25]

def best_catalyst(report,candidate,decision):
    tr={'A_PRIMARY':4,'B_HIGH_QUALITY_SECONDARY':3,'C_MARKET_NEWS':2,'D_OTHER':1}; er={'MERGER':5,'FDA_REGULATORY':5,'FINANCING':5,'CONTRACT':4,'EARNINGS':4,'BUYBACK':3,'INDEX_EVENT':3,'LEGAL':3,'PARTNERSHIP':2,'MANAGEMENT':2,'OTHER':1,'NONE':0}
    ranked=[]; now=datetime.now(timezone.utc)
    for x in news_rows(report,candidate,decision):
        h=str(x.get('headline') or x.get('title') or '').strip(); tier=source_tier(x); ev=event_type(h); dt=iso_dt(x.get('published_at') or x.get('created_at') or x.get('timestamp')); age=None
        if dt:
            if dt.tzinfo is None:dt=dt.replace(tzinfo=timezone.utc)
            age=max(0,(now-dt.astimezone(timezone.utc)).total_seconds()/3600)
        fresh=3 if age is not None and age<=24 else 2 if age is not None and age<=72 else 1
        ranked.append((tr[tier]*10+er[ev]*3+fresh,x,tier,ev))
    if not ranked:return Catalyst()
    _,x,tier,ev=max(ranked,key=lambda z:z[0]); strength='HIGH' if tier=='A_PRIMARY' and ev in {'MERGER','FDA_REGULATORY','FINANCING','CONTRACT','EARNINGS'} else 'MEDIUM' if tier in {'A_PRIMARY','B_HIGH_QUALITY_SECONDARY'} else 'LOW'
    return Catalyst(ev,strength,tier,str(x.get('headline') or x.get('title') or ''),str(x.get('source') or x.get('domain') or 'UNKNOWN'),str(x.get('published_at') or x.get('created_at') or x.get('timestamp') or '') or None,'NOT_ESTABLISHED')

def flow_metrics(bars,reference_entry_price=None):
    if not bars:return Flow()
    last=bars[-1]; close,vol=f(last.get('close')),f(last.get('volume'))
    base=[f(b.get('volume')) for b in bars[-21:-1] if f(b.get('volume')) not in (None,0)]
    vb=median(base) if base else None
    r=vol/vb if vb and vol is not None else None
    dv=close*vol if None not in (close,vol) else None
    up=down=wclvn=wclvd=0.0; pers=0
    for b in bars[-5:]:
        v=f(b.get('volume'),0.0); o,c=f(b.get('open')),f(b.get('close'))
        if vb and v>=1.5*vb and o is not None and c is not None and c>=o:pers+=1
        if o is not None and c is not None:
            if c>=o:up+=v
            else:down+=v
        wclvn+=clv(b)*v;wclvd+=v
    ud=up/max(down,1)
    wc=wclvn/wclvd if wclvd else None
    win=bars[-20:]
    lows=[f(b.get('low')) for b in win if f(b.get('low')) is not None]
    highs=[f(b.get('high')) for b in win if f(b.get('high')) is not None]
    ret=None
    if lows and highs and close is not None and max(highs)>min(lows):
        ret=max(0,min(1.5,(close-min(lows))/(max(highs)-min(lows))))
    a=atr(bars); ap=a/close*100 if a is not None and close else None

    prev_close=f(bars[-2].get('close')) if len(bars)>=2 else None
    o=f(last.get('open')); h=f(last.get('high')); l=f(last.get('low'))
    one=pct(close,prev_close)
    gap=pct(o,prev_close)
    tr=max(h-l,abs(h-prev_close),abs(l-prev_close)) if None not in (h,l,prev_close) else None
    tr_atr=tr/a if a not in (None,0) and tr is not None else None
    closes=[f(b.get('close')) for b in bars]
    s5=sma(closes,5); s20=sma(closes,20)
    ds5=pct(close,s5); ds20=pct(close,s20)
    ext_low=pct(close,min(lows)) if lows and close is not None else None
    c_loc=clv(last)
    pos_gain=pct(close,reference_entry_price) if reference_entry_price not in (None,0) else None

    # Objective single-bar behavior. This does not infer who traded.
    bar_pattern='NORMAL'
    if r is not None and r>=2.0 and c_loc<=-0.55 and tr_atr is not None and tr_atr>=0.9:
        bar_pattern='HIGH_VOLUME_REJECTION'
    elif one is not None and one>=10 and tr_atr is not None and tr_atr>=1.5 and c_loc>=0.25:
        bar_pattern='CLIMACTIC_UP_EXPANSION'
    elif one is not None and one<=-8 and tr_atr is not None and tr_atr>=1.5:
        bar_pattern='CLIMACTIC_DOWN_EXPANSION'

    score=(2 if r is not None and r>=2 else 1 if r is not None and r>=1.3 else 0)+min(pers,3)+(2 if ud>=1.5 else 1 if ud>=1.05 else 0)+(1 if wc is not None and wc>0.15 else 0)+(1 if ret is not None and ret>=0.65 else 0)
    label='STRONG' if score>=7 else 'CONSTRUCTIVE' if score>=4 else 'MIXED' if score>=2 else 'WEAK'
    return Flow(
        round(r,3) if r is not None else None,
        round(dv,2) if dv is not None else None,
        pers,
        round(ud,3),
        round(wc,3) if wc is not None else None,
        round(ret,3) if ret is not None else None,
        round(ap,2) if ap is not None else None,
        round(one,2) if one is not None else None,
        round(gap,2) if gap is not None else None,
        round(tr_atr,2) if tr_atr is not None else None,
        round(ds5,2) if ds5 is not None else None,
        round(ds20,2) if ds20 is not None else None,
        round(ext_low,2) if ext_low is not None else None,
        round(c_loc,3),
        round(pos_gain,2) if pos_gain is not None else None,
        bar_pattern,
        label
    )

def phase_for(bars,flow):
    if len(bars)<5:return 'INSUFFICIENT_DATA'

    c=f(bars[-1].get('close'))

    hi=max(
        f(b.get('high'),-1e30)
        for b in bars[-20:]
    )

    lo=min(
        f(b.get('low'),1e30)
        for b in bars[-20:]
    )

    pos=(c-lo)/(hi-lo) if c is not None and hi>lo else 0.5

    # Strong rejection remains highest priority.
    if (
        flow.bar_pattern=='HIGH_VOLUME_REJECTION'
        and pos>=0.55
    ):
        return 'FAILED_EXPANSION'

    # Large positive expansion.
    if (
        flow.one_day_pct is not None
        and flow.true_range_atr is not None
        and flow.one_day_pct>=10
        and flow.true_range_atr>=1.5
        and pos>=0.75
    ):
        return 'CLIMACTIC_EXPANSION'

    if (
        flow.atr_pct
        and flow.atr_pct>=12
        and pos<0.45
    ):
        return 'POST_SPIKE_RESET'

    if (
        flow.label=='STRONG'
        and pos>=0.8
    ):
        return 'EXPANSION'

    if (
        flow.label in {'STRONG','CONSTRUCTIVE'}
        and 0.45<=pos<0.8
    ):
        return 'RE_ACCUMULATION'

    # IMPORTANT:
    # Being near a 20-day high is NOT distribution by itself.
    #
    # Require actual negative price behaviour,
    # weak close location and elevated participation.
    if (
        pos>=0.75
        and flow.one_day_pct is not None
        and flow.one_day_pct<=-1.0
        and flow.close_location is not None
        and flow.close_location<=-0.35
        and flow.rvol_20 is not None
        and flow.rvol_20>=1.2
    ):
        return 'DISTRIBUTION_RISK'

    if (
        flow.retention_20 is not None
        and flow.retention_20>=0.6
        and flow.label in {
            'MIXED',
            'CONSTRUCTIVE'
        }
    ):
        return 'CONSOLIDATION'

    # Low position in the 20-day range is not automatically
    # a structural RESET.
    if pos<0.35:

        if (
            flow.distance_sma20_pct is not None
            and flow.distance_sma20_pct<=-3.0
        ):
            return 'RESET'

        return 'PULLBACK'

    return 'ACCUMULATION'

def capital_risk(report,candidate,cat):
    t=json.dumps({'r':report,'c':candidate},default=str).lower(); reasons=[]
    if any(x in t for x in ('shelf registration','form s-3','atm offering','at-the-market')):reasons.append('Potential shelf/ATM financing overhang detected.')
    if 'reverse split' in t:reasons.append('Reverse-split history/proposal detected.')
    if any(x in t for x in ('going concern','substantial doubt')):reasons.append('Going-concern language detected.')
    if cat.event_type=='FINANCING':reasons.append('Recent financing/offering event detected.')
    return CapitalRisk('HIGH' if len(reasons)>=2 else 'MODERATE' if reasons else 'LOW',reasons or ['No major capital-structure red flag detected in current Baby inputs.'])

def exit_monitor(flow,phase,cap,p,isready):

    qa=f(
        p.get('quote_age_seconds')
        or p.get('age_seconds')
    )

    sp=f(
        p.get('spread_pct')
    )

    if qa is not None and qa>180:
        return 'DATA_ISSUE'

    if (
        isready
        and sp is not None
        and sp>2
    ):
        return 'DATA_ISSUE'

    if cap.level=='HIGH':
        return 'REVIEW'

    if phase=='FAILED_EXPANSION':
        return 'PROTECT_PROFIT'

    if phase=='CLIMACTIC_EXPANSION':
        return 'PROTECT_PROFIT'

    if phase=='DISTRIBUTION_RISK':
        return 'REVIEW'

    # IMPORTANT:
    # URGENT_REVIEW is a position-risk state.
    #
    # Do not create an urgent warning merely because an
    # unowned research symbol is weak or low in its range.
    if flow.position_gain_pct is not None:

        breakdown = (
            flow.retention_20 is not None
            and flow.retention_20<0.25
            and flow.distance_sma20_pct is not None
            and flow.distance_sma20_pct<0
            and flow.one_day_pct is not None
            and flow.one_day_pct<=-3.0
        )

        if breakdown:
            return 'URGENT_REVIEW'

    return 'CONTINUE'

def analyze(symbol,candidate=None,report=None,decision=None):
    candidate,report,decision=candidate or {},report or {},decision or {}
    bars=bars_from(report,candidate,decision)
    reference_entry=f(
        decision.get('reference_entry_price')
        or report.get('reference_entry_price')
        or candidate.get('reference_entry_price')
    )
    flow=flow_metrics(bars,reference_entry)
    cat=best_catalyst(report,candidate,decision)
    cap=capital_risk(report,candidate,cat)
    phase=phase_for(bars,flow)
    st=setup_state(decision)
    isready=ready(decision)
    score=f(candidate.get('opportunity_score') or candidate.get('score'),0)

    evidence=(2 if score>=70 else 1 if score>=50 else 0)+(2 if flow.label in {'STRONG','CONSTRUCTIVE'} else 0)+(1 if cat.strength in {'HIGH','MEDIUM'} else 0)+(1 if phase not in {'INSUFFICIENT_DATA','RESET'} else 0)
    stage='SETUP_READY' if isready else 'SETUP_FORMING' if evidence>=5 else 'MONITOR' if evidence>=3 else 'RESEARCH' if evidence>=1 else 'DISCOVERY'
    stype='EVENT_DRIVEN_MERGER' if cat.event_type=='MERGER' else f'FLOW_PLUS_{cat.event_type}' if cat.strength=='HIGH' else 'POST_SPIKE_RESET' if phase=='POST_SPIKE_RESET' else 'FAILED_EXPANSION' if phase=='FAILED_EXPANSION' else 'BREAKOUT_MOMENTUM' if phase in {'EXPANSION','CLIMACTIC_EXPANSION'} else 'ACCUMULATION_SWING' if phase in {'ACCUMULATION','RE_ACCUMULATION','CONSOLIDATION','PULLBACK'} else phase

    p=paper(decision)
    mon=exit_monitor(flow,phase,cap,p,isready)

    facts=[]
    if candidate.get('opportunity_score',candidate.get('score')) is not None:facts.append(f"Scanner opportunity score: {candidate.get('opportunity_score',candidate.get('score'))}.")
    if flow.rvol_20 is not None:facts.append(f'20-session relative volume estimate: {flow.rvol_20:.2f}x.')
    if flow.dollar_volume is not None:facts.append(f'Latest estimated dollar volume: ${flow.dollar_volume:,.0f}.')
    facts.append(f'Elevated positive-volume persistence: {flow.persistence_5}/5 sessions.')
    if flow.retention_20 is not None:facts.append(f'20-session price-retention ratio: {flow.retention_20:.0%}.')
    if flow.one_day_pct is not None:facts.append(f'Latest one-session price move: {flow.one_day_pct:+.2f}%.')
    if flow.true_range_atr is not None:facts.append(f'Latest true range: {flow.true_range_atr:.2f}x ATR.')
    if flow.distance_sma5_pct is not None:facts.append(f'Distance from 5-session average: {flow.distance_sma5_pct:+.2f}%.')
    if flow.position_gain_pct is not None:facts.append(f'Change from monitored reference entry: {flow.position_gain_pct:+.2f}%.')
    if flow.bar_pattern!='NORMAL':facts.append(f'Latest bar pattern: {flow.bar_pattern}.')
    if cat.headline:facts.append(f'Best catalyst evidence: {cat.headline} [{cat.source_tier}].')
    for label,key in [('Current quote','quote_price'),('Planned entry','entry_price'),('Invalidation','invalidation'),('Target 1','target_1'),('Target 2','target_2')]:
        v=f(p.get(key))
        if v is not None:facts.append(f'{label}: ${v:,.2f}.')

    interp=[f'Baby classifies the market phase as {phase}.',f'Setup type: {stype}.',f'Flow condition: {flow.label}.']
    if mon=='PROTECT_PROFIT':
        if phase=='FAILED_EXPANSION':
            interp.append('Heavy participation finished with a weak close in the session range, creating a failed-expansion/profit-protection warning; this is not an automatic sell instruction.')
        else:
            interp.append('The move is extended enough to justify profit-protection review; this is not an automatic sell instruction.')
    if cat.strength!='NONE':interp.append(f'Catalyst evidence is {cat.strength}; price causality remains {cat.causality}.')
    if isready:interp.append('Existing deterministic PAPER proposal gates are satisfied.')
    elif stage in {'MONITOR','SETUP_FORMING'}:interp.append('Evidence is sufficient to keep this symbol in monitoring even though final setup-ready conditions are not satisfied.')

    contra=(cap.reasons or [])[:]
    if flow.atr_pct is not None and flow.atr_pct>=10:contra.append(f'Volatility is elevated: ATR is about {flow.atr_pct:.1f}% of price.')
    if flow.label=='WEAK':contra.append('Current flow evidence is weak.')
    if phase=='CLIMACTIC_EXPANSION':contra.append('Current session is climactically extended versus recent volatility; give-back risk is elevated.')
    if phase=='FAILED_EXPANSION':contra.append('High relative volume ended with a weak close inside the session range; distribution/rejection risk is elevated.')
    if cat.strength=='NONE':contra.append('No material company-specific catalyst is established in current Baby inputs.')
    if not contra:contra=['No major contradiction detected in current inputs; this is not proof of future performance.']

    nxt=[]
    if not isready:nxt.append('Advance only if price/flow confirmation improves without violating liquidity or quote-quality gates.')
    if flow.label in {'MIXED','WEAK'}:nxt.append('Look for renewed positive-volume persistence and stronger closes.')
    if phase in {'DISTRIBUTION_RISK','RESET'}:nxt.append('Require stabilization before upgrading the setup.')
    if phase=='PULLBACK':nxt.append('Watch for support and renewed positive flow before upgrading the setup.')
    if phase=='CLIMACTIC_EXPANSION':nxt.append('Watch for failed continuation, heavy sell volume, or loss of short-term support after the expansion.')
    if cap.level=='HIGH':nxt.append('Do not upgrade without resolving capital-structure/financing risk.')
    if not nxt:nxt=['Continue monitoring for flow decay, support failure, adverse filings, or catalyst changes.']

    evscore=min(85,30+(20 if flow.label=='STRONG' else 10 if flow.label=='CONSTRUCTIVE' else 0)+(15 if cat.strength=='HIGH' else 8 if cat.strength=='MEDIUM' else 0)+(10 if phase not in {'INSUFFICIENT_DATA','RESET'} else 0)+(10 if cap.level=='LOW' else 0))
    fp=sha256(json.dumps({'stage':stage,'phase':phase,'state':st,'ready':isready,'flow':asdict(flow),'cat':asdict(cat),'cap':asdict(cap),'mon':mon},sort_keys=True,default=str).encode()).hexdigest()[:20]
    return Intelligence(symbol.upper(),stage,phase,st,isready,stype,flow,cat,cap,facts[:12],interp[:8],contra[:8],nxt[:8],mon,evscore,fp)
