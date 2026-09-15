from inspect import signature
from investor.scoring_engine import StockScoringEngine

score_sig = signature(StockScoringEngine.score)
fund_sig = signature(StockScoringEngine._fundamental_score)

assert "primary_financial" in score_sig.parameters
assert score_sig.parameters["primary_financial"].default is None
assert "primary_financial" in fund_sig.parameters

print("V3.6.2 scoring signature contract: PASS")
