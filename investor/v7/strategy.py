class InvestmentPolicy:
    """Deterministic long-only policy used for investment testing."""
    def __init__(self,min_score=60,min_confidence=40,min_coverage=60,
                 max_positions=10,max_position_weight=.10,
                 rebalance_frequency="W-FRI"):
        self.min_score=float(min_score)
        self.min_confidence=float(min_confidence)
        self.min_coverage=float(min_coverage)
        self.max_positions=int(max_positions)
        self.max_position_weight=float(max_position_weight)
        self.rebalance_frequency=rebalance_frequency

    def eligible(self,s):
        return (not s.hard_override and s.state in {"CANDIDATE","WATCH"}
                and s.score>=self.min_score
                and s.confidence>=self.min_confidence
                and s.coverage>=self.min_coverage)

    def weights(self,signals):
        ranked=sorted((s for s in signals if self.eligible(s)),
                      key=lambda s:(s.score,s.confidence),reverse=True)[:self.max_positions]
        if not ranked:return {}
        # Equal weight prevents the score itself from becoming an unvalidated sizing model.
        w=min(self.max_position_weight,1/len(ranked))
        return {s.symbol:w for s in ranked}
