from __future__ import annotations
import math
from collections import defaultdict
import numpy as np
import pandas as pd


def _safe(v):
    try:
        x=float(v)
        return x if math.isfinite(x) else None
    except Exception:return None


def _max_drawdown_window(eq: pd.Series):
    eq=eq.dropna().astype(float)
    if eq.empty:return {}
    peak=eq.cummax();dd=eq/peak-1
    trough=dd.idxmin(); peak_date=eq.loc[:trough].idxmax()
    after=eq.loc[trough:]
    recovery=after.index[after>=eq.loc[peak_date]]
    return {"peak_date":str(pd.Timestamp(peak_date).date()),"trough_date":str(pd.Timestamp(trough).date()),
            "recovery_date":str(pd.Timestamp(recovery[0]).date()) if len(recovery) else None,
            "max_drawdown":float(dd.loc[trough]),"recovered":bool(len(recovery))}


class V75Diagnostics:
    """Evidence-first diagnostics. Describes what happened; it does not tune scores."""
    def analyze(self,curve,fills,signals,prices,benchmarks=None,requested_start=None,requested_end=None):
        c=pd.DataFrame(curve)
        c["date"]=pd.to_datetime(c.date);c=c.set_index("date").sort_index()
        eq=c.equity.astype(float); daily=eq.pct_change().dropna()
        first_fill=min((pd.Timestamp(x["execution_date"]) for x in fills),default=None)
        active=c.loc[c.index>=first_fill] if first_fill is not None else c.iloc[0:0]
        exposure=(c.gross_exposure/c.equity.replace(0,np.nan)).clip(lower=0)
        cash=(c.cash/c.equity.replace(0,np.nan))
        out={
          "requested_window":{"start":str(requested_start) if requested_start else None,"end":str(requested_end) if requested_end else None},
          "portfolio_window":{"start":str(c.index[0].date()) if len(c) else None,"end":str(c.index[-1].date()) if len(c) else None},
          "first_fill_date":str(first_fill.date()) if first_fill is not None else None,
          "idle_days_before_first_fill":int((first_fill-c.index[0]).days) if first_fill is not None and len(c) else None,
          "average_gross_exposure":_safe(exposure.mean()),"median_gross_exposure":_safe(exposure.median()),
          "average_cash_weight":_safe(cash.mean()),"max_positions":int(c.positions.max()) if len(c) else 0,
          "drawdown":_max_drawdown_window(eq),
          "active_period":self._active_period(active),
          "symbol_trading":self._symbol_trading(fills),
          "signal_diagnostics":self._signals(signals,prices),
        }
        if benchmarks:out["relative_performance"]=self._relative(eq,benchmarks)
        return out

    def _active_period(self,c):
        if len(c)<2:return {}
        s=c.equity.astype(float);r=s.pct_change().dropna();years=max((s.index[-1]-s.index[0]).days/365.25,1/365.25)
        return {"start":str(s.index[0].date()),"end":str(s.index[-1].date()),"total_return":float(s.iloc[-1]/s.iloc[0]-1),
          "cagr":float((s.iloc[-1]/s.iloc[0])**(1/years)-1),
          "annualized_volatility":float(r.std(ddof=1)*np.sqrt(252)) if len(r)>1 else None,
          "sharpe_zero_rf":float(r.mean()/r.std(ddof=1)*np.sqrt(252)) if len(r)>1 and r.std(ddof=1)>0 else None}

    def _symbol_trading(self,fills):
        x=defaultdict(lambda:{"buy_notional":0.,"sell_notional":0.,"buy_fills":0,"sell_fills":0,"slippage":0.,"fees":0.})
        for f in fills:
            d=x[f["symbol"]];side=f["side"].upper();d[side.lower()+"_notional"]+=float(f["notional"]);d[side.lower()+"_fills"]+=1
            d["slippage"]+=float(f.get("slippage",0));d["fees"]+=float(f.get("fee",0))
        return dict(sorted(x.items()))

    def _signals(self,signals,prices):
        rows=[]
        for s in signals:
            sym=s.symbol if hasattr(s,"symbol") else s["symbol"]; date=pd.Timestamp(s.date if hasattr(s,"date") else s["date"])
            score=float(s.score if hasattr(s,"score") else s["score"]); state=s.state if hasattr(s,"state") else s["state"]
            h=prices.get(sym)
            if h is None or h.empty:continue
            h=h.sort_index();ix=h.index[h.index<=date]
            if not len(ix):continue
            i=h.index.get_loc(ix[-1]);base=float(h.iloc[i].Close)
            row={"symbol":sym,"date":str(date.date()),"score":score,"state":state}
            for n in (5,21,63):row[f"r{n}"]=float(h.iloc[i+n].Close/base-1) if i+n<len(h) else None
            rows.append(row)
        if not rows:return {}
        df=pd.DataFrame(rows)
        result={"observations":len(df),"spearman_score_forward_return":{}}
        for n in (5,21,63):
            z=df[["score",f"r{n}"]].dropna()
            result["spearman_score_forward_return"][f"{n}d"]=_safe(z.corr(method="spearman").iloc[0,1]) if len(z)>=3 else None
        return result

    def _relative(self,eq,benchmarks):
        out={}
        for name,curve in benchmarks.items():
            b=pd.Series(curve,dtype=float).dropna(); common=eq.index.intersection(b.index)
            if len(common)<3:continue
            p=eq.loc[common]/eq.loc[common[0]]; q=b.loc[common]/b.loc[common[0]]
            rp=p.pct_change().dropna(); rb=q.pct_change().dropna(); active=rp-rb
            beta=float(rp.cov(rb)/rb.var()) if rb.var()>0 else None
            alpha=float((rp.mean()-(beta or 0)*rb.mean())*252) if beta is not None else None
            out[name]={"aligned_start":str(common[0].date()),"aligned_end":str(common[-1].date()),
              "portfolio_return":float(p.iloc[-1]-1),"benchmark_return":float(q.iloc[-1]-1),
              "excess_return":float(p.iloc[-1]-q.iloc[-1]),"tracking_error":_safe(active.std(ddof=1)*np.sqrt(252)),
              "information_ratio":_safe(active.mean()/active.std(ddof=1)*np.sqrt(252)) if len(active)>1 and active.std(ddof=1)>0 else None,
              "beta":beta,"alpha_zero_rf_annualized":alpha}
        return out
