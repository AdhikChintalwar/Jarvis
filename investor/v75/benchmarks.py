from __future__ import annotations
import pandas as pd
from investor.v7.benchmarks import _metrics

class AlignedBenchmarkSuite:
    def curves(self,frames,start,end,initial=100000):
        out={}
        for name,h in frames.items():
            x=h.loc[(h.index>=pd.Timestamp(start))&(h.index<=pd.Timestamp(end))]
            if len(x):
                c=x.Close.astype(float);out[name]=initial*c/c.iloc[0]
        return out
    def metrics(self,curves):return {k:_metrics(v) for k,v in curves.items()}
    def equal_weight_curve(self,prices,start,end,initial=100000):
        xs=[]
        for sym,h in prices.items():
            x=h.loc[(h.index>=pd.Timestamp(start))&(h.index<=pd.Timestamp(end))]
            if len(x)>1:
                c=x.Close.astype(float);xs.append((c/c.iloc[0]).rename(sym))
        if not xs:return None
        d=pd.concat(xs,axis=1).ffill().dropna(how="all");return initial*d.mean(axis=1)
