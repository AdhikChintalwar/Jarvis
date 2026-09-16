from __future__ import annotations
from dataclasses import dataclass,asdict
import math
import numpy as np
import pandas as pd
from investor.indicators import TechnicalIndicatorEngine

@dataclass
class HistoricalMarketSnapshot:
    current_price:float|None
    as_of:str
    average_volume_20d:float|None
    average_dollar_volume_20d:float|None
    annualized_volatility:float|None
    technical:object
    advanced_market:dict
    source:str="historical OHLCV supplied to Baby"

class HistoricalMarketSnapshotEngine:
    """Pure PIT market engine. It never downloads future bars internally."""
    def build(self,symbol,history,as_of,benchmark_history=None):
        cutoff=pd.Timestamp(as_of)
        if cutoff.tz is not None:
            cutoff=cutoff.tz_convert(None)
        h=history.copy()
        idx=pd.to_datetime(h.index)
        if getattr(idx,"tz",None) is not None: idx=idx.tz_convert(None)
        h.index=idx
        h=h.loc[h.index<=cutoff].sort_index()
        if h.empty:raise ValueError("no market bars available as-of cutoff")
        tech=TechnicalIndicatorEngine().analyze(h)
        close=h["Close"].astype(float); vol=h["Volume"].astype(float)
        ret=close.pct_change().dropna()
        rv=float(ret.tail(20).std(ddof=1)*math.sqrt(252)*100) if len(ret)>=20 else None
        av=float(vol.tail(20).mean()) if len(vol)>=1 else None
        adv=float((close*vol).tail(20).mean()) if len(vol)>=1 else None
        score=50.; positives=[]; risks=[]; known=0
        if tech.ema_20 is not None:
            known+=1
            if tech.price>tech.ema_20:score+=8;positives.append("Price is above EMA20.")
            else:score-=8;risks.append("Price is below EMA20.")
        if tech.ema_50 is not None:
            known+=1
            if tech.price>tech.ema_50:score+=8;positives.append("Price is above EMA50.")
            else:score-=8;risks.append("Price is below EMA50.")
        if tech.rsi_14 is not None:
            known+=1
            if 45<=tech.rsi_14<=70:score+=5
            elif tech.rsi_14>=80:score-=5;risks.append("RSI14 is extremely elevated.")
        if rv is not None:
            known+=1
            if rv>=80:score-=15;risks.append("Realized volatility is very high.")
            elif rv>=50:score-=8
            elif rv<25:score+=5
        # Historical relative strength against benchmark, if supplied.
        rs=None
        if benchmark_history is not None:
            b=benchmark_history.copy()
            bi=pd.to_datetime(b.index)
            if getattr(bi,"tz",None) is not None:bi=bi.tz_convert(None)
            b.index=bi;b=b.loc[b.index<=cutoff].sort_index()
            if len(h)>=21 and len(b)>=21:
                sr=close.iloc[-1]/close.iloc[-21]-1
                bc=(b["Close"] if isinstance(b,pd.DataFrame) else b).astype(float)
                br=bc.iloc[-1]/bc.iloc[-21]-1
                rs=float((sr-br)*100);known+=1
                if rs>=5:score+=8;positives.append("20D relative strength exceeds benchmark.")
                elif rs<=-5:score-=8;risks.append("20D relative strength trails benchmark.")
        conf=70.0 if known else 0.0
        advanced={
          "score":round(max(0,min(100,score)),2),"confidence":conf,
          "coverage":round(known/5*100,2),
          "signals":{"realized_volatility_20d":{"value":rv,"confidence":.80,"as_of":str(h.index[-1].date())},
                     "relative_strength_20d":{"value":rs,"confidence":.70 if rs is not None else 0}},
          "positives":positives,"risks":risks,
          "unknowns":[] if known==5 else ["some_historical_market_dimensions_unavailable"],
          "schema_version":"6.5-PIT"
        }
        return HistoricalMarketSnapshot(float(close.iloc[-1]),str(h.index[-1].date()),av,adv,rv,tech,advanced)
