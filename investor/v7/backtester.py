import math
import pandas as pd
from .execution import RealisticExecutionEngine
from .benchmarks import _metrics
from .models import PortfolioPoint

class InvestmentBacktester:
    def __init__(self,policy,execution=None):
        self.policy=policy
        self.execution=execution or RealisticExecutionEngine()

    @staticmethod
    def _close(prices,symbol,date,last=None):
        if symbol not in prices:return last
        h=prices[symbol]
        if date in h.index:return float(h.loc[date]["Close"])
        prior=h.index[h.index<=date]
        return float(h.loc[prior[-1]]["Close"]) if len(prior) else last

    def run(self,prices,signals,initial_cash=100000):
        dates=sorted(set().union(*[set(x.index) for x in prices.values()]))
        if len(dates)<2:raise ValueError("insufficient price history")
        by_date={}
        for s in signals:by_date.setdefault(pd.Timestamp(s.date).normalize(),[]).append(s)
        positions={};cash=float(initial_cash);fills=[];curve=[];last_prices={}
        pending=None
        for i,date in enumerate(dates):
            date=pd.Timestamp(date).normalize()
            # Execute yesterday/previous signal's targets at today's open.
            if pending is not None:
                equity=cash+sum(q*(self._close(prices,s,date,last_prices.get(s)) or 0)
                                for s,q in positions.items())
                positions,cash,new=self.execution.execute_to_targets(
                    pending["signal_date"],date,pending["weights"],prices,positions,cash,equity)
                fills.extend(new);pending=None
            for s in set(positions):
                p=self._close(prices,s,date,last_prices.get(s))
                if p is not None:last_prices[s]=p
            equity=cash+sum(q*last_prices.get(s,0) for s,q in positions.items())
            gross=sum(abs(q*last_prices.get(s,0)) for s,q in positions.items())
            curve.append(PortfolioPoint(str(date.date()),equity,cash,gross,len(positions)).__dict__)
            if date in by_date:
                pending={"signal_date":date,"weights":self.policy.weights(by_date[date])}
        eq=pd.Series([x["equity"] for x in curve],
                     index=pd.to_datetime([x["date"] for x in curve]))
        metrics=_metrics(eq)
        metrics["turnover_notional"]=float(sum(x.notional for x in fills))
        metrics["transaction_fees"]=float(sum(x.fee for x in fills))
        metrics["slippage_cost"]=float(sum(x.slippage for x in fills))
        metrics["fills"]=len(fills)
        metrics["final_equity"]=float(eq.iloc[-1])
        return curve,[x.__dict__ for x in fills],metrics
