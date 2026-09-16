import math
import pandas as pd
import numpy as np

def _metrics(series):
    s=pd.Series(series,dtype=float).dropna()
    if len(s)<2:return {}
    r=s.pct_change().dropna()
    years=max((s.index[-1]-s.index[0]).days/365.25,1/365.25) if isinstance(s.index,pd.DatetimeIndex) else len(s)/252
    dd=s/s.cummax()-1
    vol=r.std(ddof=1)*math.sqrt(252) if len(r)>1 else float("nan")
    return {"total_return":float(s.iloc[-1]/s.iloc[0]-1),
      "cagr":float((s.iloc[-1]/s.iloc[0])**(1/years)-1),
      "annualized_volatility":float(vol),
      "sharpe":float(r.mean()/r.std(ddof=1)*math.sqrt(252)) if len(r)>1 and r.std(ddof=1)>0 else None,
      "max_drawdown":float(dd.min())}

class BenchmarkSuite:
    def buy_hold(self,frame,start,end,initial=100000):
        h=frame.loc[(frame.index>=start)&(frame.index<=end)]
        if h.empty:return None
        c=h["Close"].astype(float)
        return initial*c/c.iloc[0]

    def equal_weight(self,prices,start,end,initial=100000):
        normalized=[]
        for _,h in prices.items():
            x=h.loc[(h.index>=start)&(h.index<=end)]
            if len(x)>1:
                c=x["Close"].astype(float)
                normalized.append(c/c.iloc[0])
        if not normalized:return None
        df=pd.concat(normalized,axis=1).ffill()
        return initial*df.mean(axis=1)

    def evaluate(self,benchmark_frames,start,end,initial=100000):
        out={}
        for name,frame in benchmark_frames.items():
            curve=self.buy_hold(frame,pd.Timestamp(start),pd.Timestamp(end),initial)
            if curve is not None:out[name]=_metrics(curve)
        return out
