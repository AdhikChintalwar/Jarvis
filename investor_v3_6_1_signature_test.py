from inspect import signature
from investor.scoring_engine import StockScoringEngine

sig = signature(StockScoringEngine.score)
assert "primary_financial" in sig.parameters
assert sig.parameters["primary_financial"].default is None

print("V3.6.1 StockScoringEngine primary_financial contract: PASS")
