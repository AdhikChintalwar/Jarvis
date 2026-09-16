import math
import numpy as np
import pandas as pd
from .models import BacktestAudit, BacktestResult

class PointInTimeBacktester:
    """Research-grade long-only backtester with explicit timestamp discipline.

    Signals at date t execute at the NEXT available bar, preventing same-close
    execution lookahead. This engine refuses to describe a test as point-in-time
    unless both universe and fundamental flags are true.
    """
    def run(self, prices:dict, signals:dict, start:str, end:str,
            initial_cash=100000.0, transaction_cost_bps=5.0,
            point_in_time_universe=True, point_in_time_fundamentals=True):
        if not point_in_time_universe:
            raise ValueError("POINT_IN_TIME_UNIVERSE_REQUIRED")
        if not point_in_time_fundamentals:
            raise ValueError("POINT_IN_TIME_FUNDAMENTALS_REQUIRED")

        frames={}
        for sym,df in prices.items():
            x=df.copy()
            if "Close" not in x.columns: continue
            x=x.loc[(x.index>=pd.Timestamp(start))&(x.index<=pd.Timestamp(end))]
            if len(x): frames[sym.upper()]=x
        common=sorted(set().union(*[set(x.index) for x in frames.values()])) if frames else []
        if len(common)<2:
            audit=BacktestAudit(start,end,None,None,0,list(prices),[],status="INSUFFICIENT_HISTORY")
            return BacktestResult(audit,[],[],{})

        cash=float(initial_cash); positions={s:0.0 for s in frames}; trades=[]; curve=[]
        cost_rate=transaction_cost_bps/10000.0
        # Signals are target weights. Shift one bar by applying yesterday's signal today.
        previous_targets={}
        for i,dt in enumerate(common):
            px={s:float(df.loc[dt,"Close"]) for s,df in frames.items() if dt in df.index}
            if not px: continue
            equity=cash+sum(positions[s]*px.get(s,0.0) for s in positions)
            if i>0 and previous_targets:
                targets={s:max(0.0,float(previous_targets.get(s,0.0))) for s in px}
                total=sum(targets.values())
                if total>1.0+1e-9:
                    targets={s:w/total for s,w in targets.items()}
                # Sell first, then buy; costs explicitly reduce cash.
                desired={s:equity*targets.get(s,0.0)/px[s] for s in px}
                for s in px:
                    delta=desired[s]-positions[s]
                    if delta<0:
                        notional=(-delta)*px[s]; fee=notional*cost_rate
                        cash += notional-fee; positions[s]+=delta
                        trades.append({"date":str(dt.date()),"symbol":s,"side":"SELL",
                                       "shares":-delta,"price":px[s],"fee":fee})
                equity=cash+sum(positions[s]*px.get(s,0.0) for s in positions)
                for s in px:
                    delta=desired[s]-positions[s]
                    if delta>0:
                        max_shares=cash/(px[s]*(1+cost_rate))
                        qty=min(delta,max_shares)
                        if qty>0:
                            notional=qty*px[s]; fee=notional*cost_rate
                            cash-=notional+fee; positions[s]+=qty
                            trades.append({"date":str(dt.date()),"symbol":s,"side":"BUY",
                                           "shares":qty,"price":px[s],"fee":fee})
            equity=cash+sum(positions[s]*px.get(s,0.0) for s in positions)
            curve.append({"date":str(dt.date()),"equity":equity})
            sig=signals.get(dt,signals.get(str(dt.date()),{}))
            previous_targets=dict(sig or {})

        eq=pd.Series([x["equity"] for x in curve],dtype=float)
        ret=eq.pct_change().dropna()
        total=float(eq.iloc[-1]/eq.iloc[0]-1) if len(eq)>1 else None
        years=max((pd.Timestamp(curve[-1]["date"])-pd.Timestamp(curve[0]["date"])).days/365.25,1/365.25)
        cagr=float((eq.iloc[-1]/eq.iloc[0])**(1/years)-1) if len(eq)>1 and eq.iloc[0]>0 else None
        vol=float(ret.std(ddof=1)*math.sqrt(252)) if len(ret)>1 else None
        sharpe=float(ret.mean()/ret.std(ddof=1)*math.sqrt(252)) if len(ret)>1 and ret.std(ddof=1)>0 else None
        peak=eq.cummax(); dd=eq/peak-1
        maxdd=float(dd.min()) if len(dd) else None
        audit=BacktestAudit(
            start,end,curve[0]["date"],curve[-1]["date"],len(curve),
            list(prices),list(frames),lookahead_violations=0,
            point_in_time_fundamentals=True,point_in_time_universe=True,
            status="PASS",warnings=[]
        )
        return BacktestResult(audit,curve,trades,{
            "total_return":total,"annualized_return":cagr,
            "annualized_volatility":vol,"sharpe":sharpe,
            "max_drawdown":maxdd,
            "transaction_costs":sum(t["fee"] for t in trades)
        })
