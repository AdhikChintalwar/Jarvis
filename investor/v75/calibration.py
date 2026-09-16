from __future__ import annotations
import numpy as np
import pandas as pd

class RobustScoreCalibration:
    """Calibration diagnostics with sample-size warnings and rank correlation."""
    def __init__(self,min_bin_n=10):self.min_bin_n=int(min_bin_n)
    def analyze(self,signals,prices,horizons=(5,21,63)):
        rows=[]
        for s in signals:
            h=prices.get(s.symbol)
            if h is None or h.empty:continue
            h=h.sort_index();dt=pd.Timestamp(s.date);ix=h.index[h.index<=dt]
            if not len(ix):continue
            i=h.index.get_loc(ix[-1]);base=float(h.iloc[i].Close)
            row={"score":float(s.score),"state":s.state,"symbol":s.symbol,"date":s.date}
            for n in horizons:row[f"r{n}"]=float(h.iloc[i+n].Close/base-1) if i+n<len(h) else np.nan
            rows.append(row)
        if not rows:return {"observations":0,"bins":[],"warning":"NO_OBSERVATIONS"}
        d=pd.DataFrame(rows);d["score_bin"]=(np.floor(d.score/10)*10).clip(0,90).astype(int).astype(str)+"-"+(np.floor(d.score/10)*10+9).clip(9,99).astype(int).astype(str)
        bins=[]
        for b,g in d.groupby("score_bin",sort=True):
            x={"score_bin":b,"n":int(len(g)),"reliable_sample":bool(len(g)>=self.min_bin_n)}
            for n in horizons:
                v=g[f"r{n}"].dropna();x[f"n_{n}d"]=int(len(v));x[f"mean_{n}d"]=float(v.mean()) if len(v) else None;x[f"median_{n}d"]=float(v.median()) if len(v) else None;x[f"positive_rate_{n}d"]=float((v>0).mean()) if len(v) else None
            bins.append(x)
        rank={}
        for n in horizons:
            z=d[["score",f"r{n}"]].dropna();rank[f"{n}d"]={"n":int(len(z)),"spearman":float(z.corr(method="spearman").iloc[0,1]) if len(z)>=3 else None}
        return {"observations":int(len(d)),"bins":bins,"rank_correlation":rank,
          "warning":"SMALL_SAMPLE_CALIBRATION; do not retune production score weights from this bounded universe alone."}
