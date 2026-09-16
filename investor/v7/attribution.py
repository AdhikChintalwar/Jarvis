import pandas as pd

class StrategyAttribution:
    def analyze(self,signals,prices):
        rows=[]
        for s in signals:
            if s.symbol not in prices:continue
            h=prices[s.symbol].sort_index();dt=pd.Timestamp(s.date)
            ix=h.index[h.index<=dt]
            if not len(ix):continue
            i=h.index.get_loc(ix[-1])
            if i+21>=len(h):continue
            ret=float(h.iloc[i+21]["Close"]/h.iloc[i]["Close"]-1)
            rows.append({"state":s.state,"risk":s.risk_level,"hard":s.hard_override,
                         "return_21d":ret})
        if not rows:return {}
        d=pd.DataFrame(rows)
        def group(col):
            return {str(k):{"n":len(g),"mean_21d":float(g.return_21d.mean()),
                            "positive_rate":float((g.return_21d>0).mean())}
                    for k,g in d.groupby(col)}
        return {"by_state":group("state"),"by_risk":group("risk"),
                "hard_override":{"n":int(d.hard.sum()),
                    "mean_21d":float(d.loc[d.hard,"return_21d"].mean()) if d.hard.any() else None}}
