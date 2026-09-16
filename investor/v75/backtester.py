from __future__ import annotations
import pandas as pd
from investor.v7.execution import RealisticExecutionEngine
from investor.v7.benchmarks import _metrics
from investor.v7.models import PortfolioPoint

class WindowedInvestmentBacktester:
    """V7.5 backtester: warm-up bars may precede start, but portfolio accounting may not."""
    def __init__(self,policy,execution=None):self.policy=policy;self.execution=execution or RealisticExecutionEngine()
    @staticmethod
    def _close(prices,symbol,date,last=None):
        h=prices.get(symbol)
        if h is None:return last
        if date in h.index:return float(h.loc[date]["Close"])
        prior=h.index[h.index<=date];return float(h.loc[prior[-1]]["Close"]) if len(prior) else last
    def run(self,prices,signals,initial_cash=100000,start=None,end=None):
        dates=sorted(set().union(*[set(x.index) for x in prices.values()]))
        start=pd.Timestamp(start).normalize() if start is not None else pd.Timestamp(dates[0]).normalize()
        end=pd.Timestamp(end).normalize() if end is not None else pd.Timestamp(dates[-1]).normalize()
        dates=[pd.Timestamp(x).normalize() for x in dates if start<=pd.Timestamp(x).normalize()<=end]
        if len(dates)<2:raise ValueError("insufficient in-window price history")
        by_date={}
        for s in signals:
            dt=pd.Timestamp(s.date).normalize()
            if start<=dt<=end:by_date.setdefault(dt,[]).append(s)
        positions={};cash=float(initial_cash);fills=[];curve=[];last_prices={};pending=None
        for date in dates:
            if pending is not None:
                equity=cash+sum(q*(self._close(prices,s,date,last_prices.get(s)) or 0) for s,q in positions.items())
                positions,cash,new=self.execution.execute_to_targets(pending["signal_date"],date,pending["weights"],prices,positions,cash,equity)
                fills.extend(new);pending=None
            for s in set(positions):
                p=self._close(prices,s,date,last_prices.get(s))
                if p is not None:last_prices[s]=p
            equity=cash+sum(q*last_prices.get(s,0) for s,q in positions.items());gross=sum(abs(q*last_prices.get(s,0)) for s,q in positions.items())
            curve.append(PortfolioPoint(str(date.date()),equity,cash,gross,len(positions)).__dict__)
            if date in by_date:pending={"signal_date":date,"weights":self.policy.weights(by_date[date])}
        eq=pd.Series([x["equity"] for x in curve],index=pd.to_datetime([x["date"] for x in curve]))
        metrics=_metrics(eq);metrics.update({"turnover_notional":float(sum(x.notional for x in fills)),"transaction_fees":float(sum(x.fee for x in fills)),"slippage_cost":float(sum(x.slippage for x in fills)),"fills":len(fills),"final_equity":float(eq.iloc[-1]),"requested_start":str(start.date()),"requested_end":str(end.date()),"actual_start":str(eq.index[0].date()),"actual_end":str(eq.index[-1].date())})
        return curve,[x.__dict__ for x in fills],metrics
