from .replay import HistoricalDecisionReplay
from .portfolio import HistoricalPortfolioSimulator
from .evaluation import PerformanceEvaluator
from .audit import V6Audit

class BabyInvestorV6:
    """Integrated historical validation shell.

    Production DecisionEngine must be injected. No fallback AI/toy scoring exists.
    """
    def __init__(self,decision_fn,max_position_weight=.10,min_score=60):
        self.replay=HistoricalDecisionReplay(decision_fn)
        self.portfolio=HistoricalPortfolioSimulator(max_position_weight,min_score)

    def run(self,snapshots,prices,start,end,cost_bps=5,universe_coverage=None):
        decisions=[self.replay.replay(s) for s in snapshots]
        dated={}
        for d in decisions: dated.setdefault(d.as_of[:10],[]).append(d)
        bt=self.portfolio.backtest(prices,dated,start,end,cost_bps=cost_bps)
        perf=PerformanceEvaluator.metrics(bt.equity_curve)
        audit=V6Audit().build(snapshots=snapshots,decisions=decisions,backtest=bt,
                              universe_coverage=universe_coverage)
        return {"decisions":[d.to_dict() for d in decisions],"backtest":bt,
                "performance":perf,"audit":audit}
