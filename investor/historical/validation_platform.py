import math
import numpy as np
import pandas as pd
from dataclasses import dataclass,asdict

@dataclass
class FoldResult:
    train_start:str; train_end:str; test_start:str; test_end:str
    train_observations:int; test_observations:int; status:str

class WalkForwardValidator:
    def folds(self,index,train_days=504,test_days=126,step_days=126):
        idx=pd.DatetimeIndex(index).sort_values().unique()
        out=[]; i=train_days
        while i+test_days<=len(idx):
            tr=idx[i-train_days:i]; te=idx[i:i+test_days]
            out.append(FoldResult(str(tr[0].date()),str(tr[-1].date()),
                str(te[0].date()),str(te[-1].date()),len(tr),len(te),"OUT_OF_SAMPLE"))
            i+=step_days
        return out

class BenchmarkEngine:
    @staticmethod
    def equal_weight(symbols):
        s=list(symbols); return {x:1/len(s) for x in s} if s else {}

    @staticmethod
    def momentum(prices,as_of,lookback=126):
        scores={}
        for sym,df in prices.items():
            x=df.loc[df.index<=pd.Timestamp(as_of),"Close"].dropna().tail(lookback+1)
            if len(x)>=lookback+1: scores[sym]=float(x.iloc[-1]/x.iloc[0]-1)
        chosen=[s for s,_ in sorted(scores.items(),key=lambda kv:kv[1],reverse=True)[:max(1,len(scores)//5)]]
        return BenchmarkEngine.equal_weight(chosen)

class ValidationAudit:
    def build(self,*,model_version,snapshots,folds,backtest):
        blocked=sum(len(s.provenance.get("blocked_future_evidence",[])) for s in snapshots)
        return {
          "model_version":model_version,
          "snapshot_count":len(snapshots),
          "blocked_future_evidence":blocked,
          "walk_forward_folds":[asdict(f) for f in folds],
          "lookahead_violations":backtest.audit.lookahead_violations,
          "survivorship_mode":backtest.audit.survivorship_mode,
          "point_in_time_fundamentals":backtest.audit.point_in_time_fundamentals,
          "point_in_time_universe":backtest.audit.point_in_time_universe,
          "backtest_status":backtest.audit.status,
          "status":"PASS" if backtest.audit.lookahead_violations==0 else "FAIL",
        }
