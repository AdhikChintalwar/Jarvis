import math
import numpy as np
import pandas as pd

class PerformanceEvaluator:
    @staticmethod
    def metrics(equity_curve,benchmark=None):
        if not equity_curve:return {}
        eq=pd.Series([x["equity"] for x in equity_curve],
                     index=pd.to_datetime([x["date"] for x in equity_curve]),dtype=float)
        r=eq.pct_change().dropna()
        downside=r[r<0]
        years=max((eq.index[-1]-eq.index[0]).days/365.25,1/365.25)
        peak=eq.cummax(); dd=eq/peak-1
        out={
          "total_return":float(eq.iloc[-1]/eq.iloc[0]-1),
          "cagr":float((eq.iloc[-1]/eq.iloc[0])**(1/years)-1),
          "annualized_volatility":float(r.std(ddof=1)*math.sqrt(252)) if len(r)>1 else None,
          "downside_deviation":float(downside.std(ddof=1)*math.sqrt(252)) if len(downside)>1 else None,
          "sharpe":float(r.mean()/r.std(ddof=1)*math.sqrt(252)) if len(r)>1 and r.std(ddof=1)>0 else None,
          "sortino":float(r.mean()/downside.std(ddof=1)*math.sqrt(252)) if len(downside)>1 and downside.std(ddof=1)>0 else None,
          "max_drawdown":float(dd.min()),
          "observations":len(eq),
        }
        if benchmark is not None:
            b=pd.Series(benchmark,dtype=float).reindex(eq.index).ffill().dropna()
            aligned=eq.reindex(b.index)
            if len(b)>1:
                out["benchmark_total_return"]=float(b.iloc[-1]/b.iloc[0]-1)
                out["excess_total_return"]=out["total_return"]-out["benchmark_total_return"]
        return out

class OutOfSampleEvaluator:
    """Aggregates only test-window results from explicit walk-forward folds."""
    @staticmethod
    def summarize(fold_metrics):
        vals=[x for x in fold_metrics if x.get("status","PASS")=="PASS"]
        if not vals:return {"folds":0,"status":"INSUFFICIENT_OOS"}
        rets=[x["total_return"] for x in vals if x.get("total_return") is not None]
        return {"folds":len(vals),"mean_oos_total_return":float(np.mean(rets)) if rets else None,
                "median_oos_total_return":float(np.median(rets)) if rets else None,
                "positive_fold_rate":float(np.mean([x>0 for x in rets])) if rets else None,
                "status":"PASS"}
