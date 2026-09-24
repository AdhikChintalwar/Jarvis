#!/usr/bin/env python3
import argparse,csv,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from baby_ui_backend.v155_intelligence import analyze
from baby_ui_backend.v156_regime import assess as assess_v156
from baby_ui_backend.v156_event_risk import assess_events
from baby_ui_backend.v156_market_context import assess_market_context

def rows(path):
    out=[]
    with open(path,newline='') as f:
        for r in csv.DictReader(f):
            for k in ('open','high','low','close','volume'):
                try:r[k]=float(r[k])
                except Exception:pass
            out.append(r)
    return sorted(out,key=lambda x:x['date'])



def context_rows(path):
    if not path:
        return []
    return rows(path)

def through_date(data,date):
    return [r for r in data if r.get('date') and r['date']<=date]

def event_rows(path):
    if not path:
        return []
    out=[]
    with open(path,newline='') as f:
        for r in csv.DictReader(f):
            out.append(dict(r))
    return out

def main():
    a=argparse.ArgumentParser()
    a.add_argument('--symbol',required=True)
    a.add_argument('--csv',required=True)
    a.add_argument('--entry-date')
    a.add_argument('--entry-price',type=float)
    a.add_argument('--exit-date')
    a.add_argument('--exit-price',type=float)
    a.add_argument('--events-csv');a.add_argument('--market-csv');a.add_argument('--smallcap-csv');a.add_argument('--sector-csv');a.add_argument('--vix-csv');a.add_argument('--out')
    z=a.parse_args()

    all_data=rows(z.csv)
    events=event_rows(z.events_csv)
    market_data=context_rows(z.market_csv)
    smallcap_data=context_rows(z.smallcap_csv)
    sector_data=context_rows(z.sector_csv)
    vix_data=context_rows(z.vix_csv)

    # Critical point-in-time rule:
    # if an exit date is supplied, do not emit later sessions into the replay timeline.
    data=[r for r in all_data if not z.exit_date or r['date']<=z.exit_date]

    timeline=[]
    entry_i=None
    entry_snapshot=None
    exit_snapshot=None

    for i,r in enumerate(data):
        if z.entry_date and r['date']==z.entry_date:entry_i=i
        decision={'status':'RESEARCH','proposal':{'payload':{'setup_status':'RESEARCH','paper_proposal':{'eligible':False,'status':'WAITING'}}}}
        if z.entry_date and z.entry_price and r['date']>=z.entry_date:
            decision['reference_entry_price']=z.entry_price
        day_end=r['date']+'T23:59:59+00:00'
        current_events=[]
        for e in events:
            et=str(
                e.get('published_at')
                or e.get('event_time')
                or e.get('timestamp')
                or e.get('created_at')
                or e.get('date')
                or ''
            )
            if not et or et[:10] <= r['date']:
                current_events.append(e)

        intel=analyze(
            z.symbol,
            {'symbol':z.symbol},
            {'bars':data[:i+1],'events':current_events},
            decision
        )
        v156=assess_v156(
            z.symbol,
            data[:i+1],
            intel,
            {'symbol':z.symbol},
            {'bars':data[:i+1]},
            decision
        )
        event_risk=assess_events(
            z.symbol,
            {'symbol':z.symbol},
            {'bars':data[:i+1],'events':current_events},
            decision,
            as_of=day_end,
        )
        market_context=assess_market_context(
            data[:i+1],
            market_rows=through_date(market_data,r['date']),
            smallcap_rows=through_date(smallcap_data,r['date']),
            sector_rows=through_date(sector_data,r['date']),
            vix_rows=through_date(vix_data,r['date']),
        )
        row={
            'date':r['date'],
            'open':r.get('open'),
            'high':r.get('high'),
            'low':r.get('low'),
            'close':r.get('close'),
            'volume':r.get('volume'),
            'stage':intel.stage,
            'phase':intel.phase,
            'flow_label':intel.flow.label,
            'rvol_20':intel.flow.rvol_20,
            'retention_20':intel.flow.retention_20,
            'flow_retention':intel.flow.retention_20,  # compatibility alias
            'one_day_pct':intel.flow.one_day_pct,
            'gap_pct':intel.flow.gap_pct,
            'true_range_atr':intel.flow.true_range_atr,
            'distance_sma5_pct':intel.flow.distance_sma5_pct,
            'distance_sma20_pct':intel.flow.distance_sma20_pct,
            'extension_from_20d_low_pct':intel.flow.extension_from_20d_low_pct,
            'close_location':intel.flow.close_location,
            'position_gain_pct':intel.flow.position_gain_pct,
            'bar_pattern':intel.flow.bar_pattern,
            'monitoring_signal':intel.monitoring_signal,
            'evidence_score':intel.evidence_score,
            'confidence':intel.evidence_score,  # compatibility alias
            'instrument_profile':v156.instrument_profile,
            'liquidity_profile':v156.liquidity_profile,
            'volatility_profile':v156.volatility_profile,
            'behavior_regime':v156.behavior_regime,
            'research_state':v156.research_state,
            'position_state':v156.position_state,
            'flow_trend':v156.flow_trend,
            'profile_confidence':v156.profile_confidence,
            'move_atr':v156.move_atr,
            'sma20_distance_atr':v156.sma20_distance_atr,
            'volume_z_proxy':v156.volume_z_proxy,
            'catalyst_regime':event_risk.catalyst_regime,
            'catalyst_strength':event_risk.catalyst_strength,
            'catalyst_source_tier':event_risk.catalyst_source_tier,
            'catalyst_headline':event_risk.catalyst_headline,
            'catalyst_published_at':event_risk.catalyst_published_at,
            'catalyst_causality':event_risk.catalyst_causality,
            'structural_risk_level':event_risk.structural_risk_level,
            'structural_risk_score':event_risk.structural_risk_score,
            'structural_risk_reasons':event_risk.structural_risk_reasons,
            'events_seen':event_risk.events_seen,
            'primary_events_seen':event_risk.primary_events_seen,
            'latest_event_time':event_risk.latest_event_time,
            'event_conflicts':event_risk.conflicting_evidence,
            'market_regime':market_context.market_regime,
            'broad_market_trend':market_context.broad_market_trend,
            'smallcap_trend':market_context.smallcap_trend,
            'sector_trend':market_context.sector_trend,
            'volatility_regime':market_context.volatility_regime,
            'relative_strength_5d':market_context.relative_strength_5d,
            'relative_strength_20d':market_context.relative_strength_20d,
            'breadth_proxy':market_context.breadth_proxy,
            'context_signal':market_context.context_signal,
            'market_context_reasons':market_context.rationale,
            'market_context_conflicts':market_context.contradictions,
        }
        timeline.append(row)
        if z.entry_date and r['date']==z.entry_date: entry_snapshot=row
        if z.exit_date and r['date']==z.exit_date: exit_snapshot=row

    stats={}
    if entry_i is not None and z.entry_price:
        after=data[entry_i:]
        if after:
            stats={
                'mfe_pct':(max(float(r['high']) for r in after)/z.entry_price-1)*100,
                'mae_pct':(min(float(r['low']) for r in after)/z.entry_price-1)*100
            }
    if z.entry_price and z.exit_price:
        stats['realized_pct']=(z.exit_price/z.entry_price-1)*100

    result={
        'symbol':z.symbol,
        'entry_date':z.entry_date,
        'entry_price':z.entry_price,
        'exit_date':z.exit_date,
        'exit_price':z.exit_price,
        'stats':stats,
        'entry_snapshot':entry_snapshot,
        'exit_snapshot':exit_snapshot,
        'timeline':timeline
    }
    txt=json.dumps(result,indent=2)
    if z.out:Path(z.out).write_text(txt);print(z.out)
    else:print(txt)

if __name__=='__main__':main()
