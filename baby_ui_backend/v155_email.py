from html import escape
from .email_branding import email_shell

def e(v):return escape('' if v is None else str(v))

def choose_event(cur,prev=None):
    p=(prev or {}).get('snapshot') or prev or {}
    if cur.monitoring_signal=='DATA_ISSUE':return 'DATA_ISSUE'
    if cur.ready:return None
    if not p:return 'NEW_RESEARCH_CANDIDATE' if cur.stage in {'RESEARCH','MONITOR','SETUP_FORMING'} else None
    old_stage=str(p.get('stage') or '');old_signal=str(p.get('monitoring_signal') or '');old_head=((p.get('catalyst') or {}).get('headline') or '')
    if cur.catalyst.headline and cur.catalyst.headline!=old_head and cur.catalyst.strength in {'HIGH','MEDIUM'}:return 'CATALYST_UPDATE'
    if cur.monitoring_signal=='URGENT_REVIEW' and old_signal!='URGENT_REVIEW':return 'EXIT_WARNING'
    if cur.monitoring_signal=='REVIEW' and old_signal=='CONTINUE':return 'SETUP_WEAKENING'
    order={'DISCOVERY':0,'RESEARCH':1,'MONITOR':2,'SETUP_FORMING':3,'SETUP_READY':4}
    if order.get(cur.stage,0)>order.get(old_stage,0):return 'MONITORING_STARTED' if cur.stage=='MONITOR' else 'SETUP_IMPROVING'
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

def build_email(x,event,market_context=None):
    c=x.catalyst
    event_title=event.replace('_',' ')
    context_lines=_context_lines(market_context)

    body=f'''<h1 style="font-size:27px;margin:12px 0 4px;color:#eef7ff">{e(x.symbol)} — {e(event_title)}</h1>
<div style="color:#7f96aa;font-size:13px;margin-bottom:20px">Stage: {e(x.stage)} · Phase: {e(x.phase)} · Setup type: {e(x.setup_type)}</div>

<div style="padding:15px;border:1px solid #21455d;background:#0a1b29;border-radius:12px;margin:18px 0">
<div style="color:#67dff0;font-size:11px;font-weight:800;letter-spacing:.12em">OBSERVED FACTS</div>
<ul style="color:#b3c3d1;font-size:13px;line-height:1.65;padding-left:20px">{_li(x.observed_facts)}</ul></div>

<div style="margin:24px 0"><div style="color:#67dff0;font-size:11px;font-weight:800;letter-spacing:.12em;margin-bottom:9px">WHY BABY NOTICED / WHAT CHANGED</div>
<ul style="color:#b3c3d1;font-size:13px;line-height:1.65;padding-left:20px">{_li(_change_lines(x,event))}</ul></div>

<div style="margin:24px 0"><div style="color:#67dff0;font-size:11px;font-weight:800;letter-spacing:.12em;margin-bottom:9px">CATALYST / NEWS</div>
<div style="color:#eef7ff;font-weight:700">{e(c.headline or 'No material company-specific catalyst established.')}</div>
<div style="color:#71899e;font-size:12px;margin-top:6px">Type: {e(c.event_type)} · Strength: {e(c.strength)} · Source tier: {e(c.source_tier)}<br>Causality: {e(c.causality)}</div></div>

<div style="margin:24px 0"><div style="color:#67dff0;font-size:11px;font-weight:800;letter-spacing:.12em;margin-bottom:9px">PRICE + FLOW</div>
<ul style="color:#b3c3d1;font-size:13px;line-height:1.65;padding-left:20px">{_li(_flow_lines(x))}</ul></div>

<div style="margin:24px 0"><div style="color:#67dff0;font-size:11px;font-weight:800;letter-spacing:.12em;margin-bottom:9px">CAPITAL STRUCTURE RISK</div>
<ul style="color:#b3c3d1;font-size:13px;line-height:1.65;padding-left:20px">{_li(_capital_lines(x))}</ul></div>

<div style="margin:24px 0"><div style="color:#67dff0;font-size:11px;font-weight:800;letter-spacing:.12em;margin-bottom:9px">MARKET CONTEXT</div>
<ul style="color:#b3c3d1;font-size:13px;line-height:1.65;padding-left:20px">{_li(context_lines)}</ul></div>

<div style="margin:24px 0"><div style="color:#67dff0;font-size:11px;font-weight:800;letter-spacing:.12em;margin-bottom:9px">BABY INTERPRETATION</div>
<ul style="color:#b3c3d1;font-size:13px;line-height:1.65;padding-left:20px">{_li(x.interpretation)}</ul></div>

<div style="margin:24px 0"><div style="color:#67dff0;font-size:11px;font-weight:800;letter-spacing:.12em;margin-bottom:9px">CONTRADICTING EVIDENCE</div>
<ul style="color:#b3c3d1;font-size:13px;line-height:1.65;padding-left:20px">{_li(x.contradicting_evidence)}</ul></div>

<div style="margin:24px 0"><div style="color:#67dff0;font-size:11px;font-weight:800;letter-spacing:.12em;margin-bottom:9px">NEXT CONDITION TO WATCH</div>
<ul style="color:#b3c3d1;font-size:13px;line-height:1.65;padding-left:20px">{_li(x.next_conditions)}</ul></div>

<div style="margin:24px 0"><div style="color:#67dff0;font-size:11px;font-weight:800;letter-spacing:.12em;margin-bottom:9px">WHAT WOULD MAKE BABY CHANGE ITS MIND</div>
<ul style="color:#b3c3d1;font-size:13px;line-height:1.65;padding-left:20px">{_li(_change_mind_lines(x))}</ul></div>

<div style="padding:14px;border:1px solid #293d58;background:#0c1725;border-radius:11px;color:#93a9bd;font-size:12px;line-height:1.65">
STATUS: <b style="color:#eef7ff">{e(x.monitoring_signal)}</b><br>
Evidence score: {x.evidence_score}/100 — research attractiveness, not a probability.<br>
Quantity is USER_SELECTED. No order is placed by this email.</div>'''

    html=email_shell(event_title,f'{x.symbol}: Baby research state changed.',body)

    text='\n'.join([
        f'BABY — {event}',x.symbol,f'Stage: {x.stage}',f'Phase: {x.phase}',f'Setup type: {x.setup_type}','',
        'OBSERVED FACTS',*[f'- {v}' for v in x.observed_facts],'',
        'WHY BABY NOTICED / WHAT CHANGED',*[f'- {v}' for v in _change_lines(x,event)],'',
        'CATALYST / NEWS',f'- {c.headline or "No material company-specific catalyst established."}',
        f'- Type: {c.event_type}; strength: {c.strength}; source tier: {c.source_tier}',
        f'- Causality: {c.causality}','',
        'PRICE + FLOW',*[f'- {v}' for v in _flow_lines(x)],'',
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
    return f"Baby — {x.symbol} {event_title.title()}",text,html
