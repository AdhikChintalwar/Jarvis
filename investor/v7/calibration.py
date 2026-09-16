import pandas as pd
import numpy as np

class ScoreCalibration:
    BINS=[0,40,50,60,70,80,101]
    LABELS=["<40","40-49","50-59","60-69","70-79","80+"]

    def analyze(self,signals,prices,horizons=(5,21,63)):
        rows=[]
        for s in signals:
            if s.symbol not in prices:continue
            h=prices[s.symbol].sort_index()
            dt=pd.Timestamp(s.date)
            prior=h.index[h.index<=dt]
            if not len(prior):continue
            i=h.index.get_loc(prior[-1])
            base=float(h.iloc[i]["Close"])
            row={"score":s.score,"state":s.state,"confidence":s.confidence}
            for n in horizons:
                row[f"r{n}"]=float(h.iloc[i+n]["Close"]/base-1) if i+n<len(h) else None
            rows.append(row)
        if not rows:return {"observations":0,"bins":[]}
        df=pd.DataFrame(rows)
        df["bin"]=pd.cut(df.score,self.BINS,labels=self.LABELS,right=False)
        bins=[]
        for b,g in df.groupby("bin",observed=True):
            x={"score_bin":str(b),"n":len(g)}
            for n in horizons:
                v=g[f"r{n}"].dropna()
                x[f"mean_{n}d"]=float(v.mean()) if len(v) else None
                x[f"median_{n}d"]=float(v.median()) if len(v) else None
                x[f"positive_rate_{n}d"]=float((v>0).mean()) if len(v) else None
            bins.append(x)
        return {"observations":len(df),"bins":bins}
