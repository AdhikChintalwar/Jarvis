from html import escape
from .email_branding import email_shell

def e(v):return escape('' if v is None else str(v))

def research_email_eligible(cur):
    """Strict positive-alert gate; discovery stays internal until useful."""
    stage=str(getattr(cur,'stage','') or '').upper()
    phase=str(getattr(cur,'phase','') or '').upper()
    setup_type=str(getattr(cur,'setup_type','') or '').upper()
    flow=getattr(cur,'flow',None)
    flow_label=str(getattr(flow,'label','') or '').upper()
    catalyst=getattr(cur,'catalyst',None)
    catalyst_strength=str(getattr(catalyst,'strength','NONE') or 'NONE').upper()
    signal=str(getattr(cur,'monitoring_signal','') or '').upper()
    if signal=='DATA_ISSUE':return False
    if stage not in {'MONITOR','SETUP_FORMING'}:return False
    if phase in {'','UNKNOWN','INSUFFICIENT_DATA'}:return False
    if setup_type in {'','UNKNOWN','INSUFFICIENT_DATA'}:return False
    if flow_label in {'','UNKNOWN','INSUFFICIENT_DATA'}:return False
    meaningful_flow=flow_label in {'STRONG','CONSTRUCTIVE'}
    meaningful_catalyst=catalyst_strength in {'HIGH','MEDIUM'}
    return meaningful_flow or meaningful_catalyst


def choose_event(cur,prev=None):
    p=(prev or {}).get('snapshot') or prev or {}
    if not p:
        if cur.ready:return None
        if not research_email_eligible(cur):return None
        return 'NEW_RESEARCH_CANDIDATE'
    old_stage=str(p.get('stage') or '')
    old_signal=str(p.get('monitoring_signal') or '')
    old_head=((p.get('catalyst') or {}).get('headline') or '')
    if cur.monitoring_signal=='DATA_ISSUE':
        return 'DATA_ISSUE' if old_signal!='DATA_ISSUE' else None
    if cur.ready:return None
    if cur.catalyst.headline and cur.catalyst.headline!=old_head and cur.catalyst.strength in {'HIGH','MEDIUM'}:return 'CATALYST_UPDATE'
    if cur.monitoring_signal=='URGENT_REVIEW' and old_signal!='URGENT_REVIEW':return 'EXIT_WARNING'
    if cur.monitoring_signal=='REVIEW' and old_signal=='CONTINUE':return 'SETUP_WEAKENING'
    order={'DISCOVERY':0,'RESEARCH':1,'MONITOR':2,'SETUP_FORMING':3,'SETUP_READY':4}
    if order.get(cur.stage,0)>order.get(old_stage,0):
        if not research_email_eligible(cur):return None
        return 'MONITORING_STARTED' if cur.stage=='MONITOR' else 'SETUP_IMPROVING'
    return None

def _li(rows):
    rows=list(rows or [])
    if not rows:rows=['No additional evidence available in this snapshot.']
    return ''.join(f"<li style='margin:0 0 8px'>{e(v)}</li>" for v in rows)

def _num(v,fmt='{:.2f}'):
    try:return fmt.format(float(v))
    except Exception:return 'UNKNOWN'

def _context_lines(context):
    if not isinstance(context,dict) or not context:
        return ['Market/sector context is not present in this email snapshot; Baby does not infer it.']
    rows=[]
    for k,label in [
        ('market_regime','Market regime'),
        ('broad_market_trend','Broad market trend'),
        ('smallcap_trend','Small-cap trend'),
        ('sector_trend','Sector trend'),
        ('volatility_regime','Volatility regime'),
        ('context_signal','Context signal'),
    ]:
        v=context.get(k)
        if v not in (None,'','UNKNOWN'):
            rows.append(f'{label}: {v}.')
    for v in context.get('contradictions') or []:
        rows.append(str(v))
    return rows or ['Market context was supplied but contains no decision-grade fields.']

def _change_lines(x,event):
    out=[
        f'Meaningful-change event: {event.replace("_"," ")}.',
        f'Current research stage: {x.stage}.',
        f'Current phase: {x.phase}.',
        f'Current monitoring status: {x.monitoring_signal}.',
    ]
    if x.setup_type and x.setup_type!='UNKNOWN':
        out.append(f'Setup family: {x.setup_type}.')
    return out

def _flow_lines(x):
    f=x.flow
    out=[f'Flow condition: {f.label}.']
    if f.rvol_20 is not None:out.append(f'20-day relative volume: {_num(f.rvol_20)}x.')
    if f.persistence_5 is not None:out.append(f'Positive-volume persistence (5-bar window): {f.persistence_5}.')
    if f.up_down_volume_ratio_5 is not None:out.append(f'Up/down volume ratio (5-bar): {_num(f.up_down_volume_ratio_5)}.')
    if f.weighted_clv_5 is not None:out.append(f'Weighted close-location value (5-bar): {_num(f.weighted_clv_5)}.')
    if f.retention_20 is not None:out.append(f'20-day move retention: {_num(f.retention_20)}.')
    if f.atr_pct is not None:out.append(f'ATR as percent of price: {_num(f.atr_pct)}%.')
    if f.dollar_volume is not None:out.append(f'Observed dollar volume: ${_num(f.dollar_volume,"{:,.0f}")}.')
    return out

def _capital_lines(x):
    cap=x.capital_risk
    out=[f'Capital-structure risk level: {cap.level}.']
    for r in cap.reasons or []:out.append(str(r))
    if len(out)==1 and cap.level=='LOW':
        out.append('No elevated capital-structure risk reason is present in this snapshot.')
    return out

def _change_mind_lines(x):
    out=list(x.next_conditions or [])
    if x.monitoring_signal in {'CONTINUE','NO_POSITION'}:
        out.append('Baby would become more cautious if flow weakens, support fails, data quality deteriorates, or adverse company evidence appears.')
    elif x.monitoring_signal in {'REVIEW','URGENT_REVIEW','PROTECT_PROFIT'}:
        out.append('Baby would become less cautious only if deterioration stabilizes and conflicting evidence resolves with trusted data.')
    elif x.monitoring_signal=='DATA_ISSUE':
        out.append('Baby will not upgrade or downgrade from the intraday signal until trustworthy data is restored.')
    return out

def _plan_lines(paper):
    p=paper if isinstance(paper,dict) else {}
    rows=[]
    fields=[('Current quote','quote_price','money'),('Bid','bid','money'),('Ask','ask','money'),('Spread','spread_pct','pct'),('Quote age','quote_age_seconds','seconds'),('Planned entry','entry_price','money'),('Invalidation','invalidation','money'),('Target 1','target_1','money'),('Target 2','target_2','money'),('R/R Target 1','rr_target_1','ratio'),('R/R Target 2','rr_target_2','ratio')]
    for label,key,kind in fields:
        v=p.get(key)
        if v is None:continue
        try:
            n=float(v)
            if kind=='money':val=f'${n:,.2f}'
            elif kind=='pct':val=f'{n:.2f}%'
            elif kind=='seconds':val=f'{n:.0f} seconds'
            elif kind=='ratio':val=f'{n:.2f}'
            else:val=str(v)
        except Exception:val=str(v)
        rows.append(f'{label}: {val}.')
    if not rows:rows.append('Deterministic trade-plan levels are not ready in this research snapshot; Baby is monitoring evidence only.')
    return rows

def build_email(x,event,market_context=None,company_name=None,paper=None):
    c=x.catalyst
    event_title=event.replace('_',' ')
    context_lines=_context_lines(market_context)
    company=str(company_name or '').strip()
    display_name=f'{x.symbol} — {company}' if company and company.upper()!=x.symbol.upper() else x.symbol
    plan_lines=_plan_lines(paper)

    body=f'''<h1 style="font-size:27px;margin:12px 0 4px;color:#102a43">{e(display_name)}</h1>
<div style="color:#1769aa;font-size:12px;font-weight:800;letter-spacing:.10em;margin-bottom:7px">{e(event_title)}</div>
<div style="color:#627d98;font-size:13px;margin-bottom:20px">Stage: {e(x.stage)} · Phase: {e(x.phase)} · Setup type: {e(x.setup_type)}</div>

<div style="padding:15px;border:1px solid #c9d9e8;background:#f4f8fc;border-radius:12px;margin:18px 0">
<div style="color:#1769aa;font-size:11px;font-weight:800;letter-spacing:.12em">OBSERVED FACTS</div>
<ul style="color:#486581;font-size:13px;line-height:1.65;padding-left:20px">{_li(x.observed_facts)}</ul></div>

<div style="margin:24px 0"><div style="color:#1769aa;font-size:11px;font-weight:800;letter-spacing:.12em;margin-bottom:9px">WHY BABY NOTICED / WHAT CHANGED</div>
<ul style="color:#486581;font-size:13px;line-height:1.65;padding-left:20px">{_li(_change_lines(x,event))}</ul></div>

<div style="margin:24px 0"><div style="color:#1769aa;font-size:11px;font-weight:800;letter-spacing:.12em;margin-bottom:9px">CATALYST / NEWS</div>
<div style="color:#102a43;font-weight:700">{e(c.headline or 'No material company-specific catalyst established.')}</div>
<div style="color:#627d98;font-size:12px;margin-top:6px">Type: {e(c.event_type)} · Strength: {e(c.strength)} · Source tier: {e(c.source_tier)}<br>Causality: {e(c.causality)}</div></div>

<div style="margin:24px 0"><div style="color:#1769aa;font-size:11px;font-weight:800;letter-spacing:.12em;margin-bottom:9px">PRICE + FLOW</div>
<ul style="color:#486581;font-size:13px;line-height:1.65;padding-left:20px">{_li(_flow_lines(x))}</ul></div>

<div style="margin:24px 0"><div style="color:#1769aa;font-size:11px;font-weight:800;letter-spacing:.12em;margin-bottom:9px">RESEARCH / TRADE PLAN SNAPSHOT</div>
<ul style="color:#486581;font-size:13px;line-height:1.65;padding-left:20px">{_li(plan_lines)}</ul></div>

<div style="margin:24px 0"><div style="color:#1769aa;font-size:11px;font-weight:800;letter-spacing:.12em;margin-bottom:9px">CAPITAL STRUCTURE RISK</div>
<ul style="color:#486581;font-size:13px;line-height:1.65;padding-left:20px">{_li(_capital_lines(x))}</ul></div>

<div style="margin:24px 0"><div style="color:#1769aa;font-size:11px;font-weight:800;letter-spacing:.12em;margin-bottom:9px">MARKET CONTEXT</div>
<ul style="color:#486581;font-size:13px;line-height:1.65;padding-left:20px">{_li(context_lines)}</ul></div>

<div style="margin:24px 0"><div style="color:#1769aa;font-size:11px;font-weight:800;letter-spacing:.12em;margin-bottom:9px">BABY INTERPRETATION</div>
<ul style="color:#486581;font-size:13px;line-height:1.65;padding-left:20px">{_li(x.interpretation)}</ul></div>

<div style="margin:24px 0"><div style="color:#1769aa;font-size:11px;font-weight:800;letter-spacing:.12em;margin-bottom:9px">CONTRADICTING EVIDENCE</div>
<ul style="color:#486581;font-size:13px;line-height:1.65;padding-left:20px">{_li(x.contradicting_evidence)}</ul></div>

<div style="margin:24px 0"><div style="color:#1769aa;font-size:11px;font-weight:800;letter-spacing:.12em;margin-bottom:9px">NEXT CONDITION TO WATCH</div>
<ul style="color:#486581;font-size:13px;line-height:1.65;padding-left:20px">{_li(x.next_conditions)}</ul></div>

<div style="margin:24px 0"><div style="color:#1769aa;font-size:11px;font-weight:800;letter-spacing:.12em;margin-bottom:9px">WHAT WOULD MAKE BABY CHANGE ITS MIND</div>
<ul style="color:#486581;font-size:13px;line-height:1.65;padding-left:20px">{_li(_change_mind_lines(x))}</ul></div>

<div style="padding:14px;border:1px solid #d2deea;background:#f7fafd;border-radius:11px;color:#526d82;font-size:12px;line-height:1.65">
STATUS: <b style="color:#102a43">{e(x.monitoring_signal)}</b><br>
Evidence score: {x.evidence_score}/100 — research attractiveness, not a probability.<br>
Quantity is USER_SELECTED. No order is placed by this email.</div>'''

    html=email_shell(event_title,f'{display_name}: Baby research state changed.',body)

    text='\n'.join([
        f'BABY — {event}',display_name,f'Stage: {x.stage}',f'Phase: {x.phase}',f'Setup type: {x.setup_type}','',
        'OBSERVED FACTS',*[f'- {v}' for v in x.observed_facts],'',
        'WHY BABY NOTICED / WHAT CHANGED',*[f'- {v}' for v in _change_lines(x,event)],'',
        'CATALYST / NEWS',f'- {c.headline or "No material company-specific catalyst established."}',
        f'- Type: {c.event_type}; strength: {c.strength}; source tier: {c.source_tier}',
        f'- Causality: {c.causality}','',
        'PRICE + FLOW',*[f'- {v}' for v in _flow_lines(x)],'',
        'RESEARCH / TRADE PLAN SNAPSHOT',*[f'- {v}' for v in plan_lines],'',
        'CAPITAL STRUCTURE RISK',*[f'- {v}' for v in _capital_lines(x)],'',
        'MARKET CONTEXT',*[f'- {v}' for v in context_lines],'',
        'BABY INTERPRETATION',*[f'- {v}' for v in x.interpretation],'',
        'CONTRADICTING EVIDENCE',*[f'- {v}' for v in x.contradicting_evidence],'',
        'NEXT CONDITION TO WATCH',*[f'- {v}' for v in x.next_conditions],'',
        'WHAT WOULD MAKE BABY CHANGE ITS MIND',*[f'- {v}' for v in _change_mind_lines(x)],'',
        f'STATUS: {x.monitoring_signal}',
        f'Evidence score: {x.evidence_score}/100 (research attractiveness, not a probability).',
        'Quantity is USER_SELECTED. No order is placed by email.',
        'AI execution authority: NONE. Real-money execution: DISABLED.'
    ])
    subject_name=f'{x.symbol} ({company})' if company and company.upper()!=x.symbol.upper() else x.symbol
    return f"Baby — {subject_name} — {event_title.title()}",text,html
