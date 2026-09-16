import pandas as pd
from investor.point_in_time import PointInTimeBacktester

class HistoricalPortfolioSimulator:
    """Converts historical Baby decisions into target weights.

    WAIT/REJECT and hard-risk decisions receive zero long allocation. Candidate
    weights are capped and normalized; actual execution remains next-bar in V5.
    """
    def __init__(self,max_position_weight=.10,min_score=60.0):
        self.max_position_weight=float(max_position_weight)
        self.min_score=float(min_score)

    def targets(self,decisions):
        eligible=[d for d in decisions if not d.hard_override and
                  d.state in {"CANDIDATE","WATCH"} and
                  d.score is not None and d.score>=self.min_score]
        if not eligible:return {}
        raw={d.symbol:min(self.max_position_weight,max(0.0,d.score/100*self.max_position_weight)) for d in eligible}
        # Keep cash when caps don't consume 100%; never lever.
        return raw

    def backtest(self,prices,dated_decisions,start,end,initial_cash=100000,cost_bps=5):
        signals={}
        for dt,ds in dated_decisions.items():
            signals[pd.Timestamp(dt)]=self.targets(ds)
        return PointInTimeBacktester().run(prices,signals,start,end,initial_cash,cost_bps,
            point_in_time_universe=True,point_in_time_fundamentals=True)
