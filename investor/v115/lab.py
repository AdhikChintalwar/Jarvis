from dataclasses import dataclass,asdict
from collections import defaultdict
from uuid import uuid4
from .models import ExperimentResult
from .integrity import PointInTimeAudit
from .metrics import performance,trade_stats
from .calibration import calibrate
from .registry import ExperimentRegistry

@dataclass(frozen=True)
class StrategyConfig:
    min_score:float=62; min_confidence:float=60; min_coverage:float=65
    allowed_states:tuple=('CANDIDATE','TOP_RESEARCH'); blocked_expectations:tuple=()
    blocked_risk:tuple=('VERY_HIGH','EXTREME'); require_setup:bool=False
    max_positions:int=10; position_weight:float=.10; slippage_bps:float=5; fee_bps:float=1

class HistoricalStrategyLab:
    """Evaluation-only V11.5 lab. It never mutates V11 scoring parameters or submits orders."""
    def __init__(self,registry=None): self.audit=PointInTimeAudit(); self.registry=registry or ExperimentRegistry()
    def eligible(self,d,c):
        return (not d.hard_risk and d.state in c.allowed_states and d.score>=c.min_score and d.confidence>=c.min_confidence and d.coverage>=c.min_coverage
                and d.risk_level not in c.blocked_risk and d.expectations not in c.blocked_expectations and (not c.require_setup or d.setup in ('AT_PULLBACK_ZONE','BREAKOUT_TRIGGERED')))
    def run(self,decisions,bars,config=StrategyConfig(),initial_cash=100000,*,integrity_flags=None,benchmark_curves=None,record=True):
        integrity_flags=integrity_flags or {}; integ=self.audit.audit(decisions,**integrity_flags)
        if integ['status']=='FAIL':
            return ExperimentResult('BLOCKED-'+uuid4().hex[:10],asdict(config),{'status':'BLOCKED_PIT_VIOLATION'}, {},{}, {},integ,[],[],['Backtest blocked by lookahead violation.'])
        px=defaultdict(dict)
        for b in bars:px[b.symbol][b.date]=b
        dates=sorted({b.date for b in bars}); by_date=defaultdict(list)
        for d in decisions:by_date[d.signal_time[:10]].append(d)
        cash=float(initial_cash); pos={}; pending=[]; curve=[]; trades=[]; calibration_rows=[]
        for i,date in enumerate(dates):
            # execute prior-date signals at current OPEN: strict signal T -> next bar
            for d in pending:
                b=px[d.symbol].get(date)
                if not b or b.open<=0: continue
                equity=cash+sum(q*px[s].get(date,px[s].get(prev_date)).close for s,q in pos.items() if px[s].get(date) or px[s].get(prev_date))
                target=min(equity*config.position_weight,cash); fill=b.open*(1+config.slippage_bps/10000); qty=int(target/fill)
                if qty>0 and len(pos)<config.max_positions:
                    cost=qty*fill; fee=cost*config.fee_bps/10000
                    if cost+fee<=cash: cash-=cost+fee; pos[d.symbol]=pos.get(d.symbol,0)+qty; trades.append({'symbol':d.symbol,'signal_date':d.signal_time[:10],'fill_date':date,'side':'BUY','qty':qty,'price':fill,'fee':fee,'pnl':None})
            pending=[]
            equity=cash
            for s,q in pos.items():
                b=px[s].get(date); equity+=q*(b.close if b else 0)
            curve.append({'date':date,'equity':equity,'cash':cash,'positions':len(pos)})
            # diagnostics: next-bar close return for every decision where available
            if i+1<len(dates):
                nd=dates[i+1]
                for d in by_date.get(date,[]):
                    b0=px[d.symbol].get(date); b1=px[d.symbol].get(nd)
                    if b0 and b1 and b0.close>0: calibration_rows.append({'score':d.score,'confidence':d.confidence,'coverage':d.coverage,'forward_return':b1.close/b0.close-1})
            pending=[d for d in by_date.get(date,[]) if self.eligible(d,config)]
            prev_date=date
        metrics=performance(curve); metrics.update(trade_stats(trades)); metrics['signals']=len(decisions); metrics['eligible_signals']=sum(self.eligible(d,config) for d in decisions)
        benchmarks={k:performance(v) for k,v in (benchmark_curves or {}).items()}
        # chronological 60/20/20 diagnostic only; no optimization on test
        n=len(decisions); ordered=sorted(decisions,key=lambda x:x.signal_time); a=int(n*.6); b=int(n*.8)
        wf={'method':'CHRONOLOGICAL_60_20_20_DIAGNOSTIC','train_n':a,'validation_n':max(0,b-a),'untouched_test_n':max(0,n-b),'parameter_tuning':'DISABLED_BY_DEFAULT','test_set_used_for_selection':False}
        warnings=list(integ.get('limitations',[]))
        expid='V115-'+uuid4().hex[:12]
        result=ExperimentResult(expid,asdict(config),metrics,benchmarks,calibrate(calibration_rows),wf,integ,trades,curve,warnings)
        if record: result.metrics['registry']=self.registry.record(expid,result.config,result.to_dict())
        return result
