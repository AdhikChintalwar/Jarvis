from types import SimpleNamespace
from investor.financial_engine import FinancialEngine
def i(v,s,c):return {"value":v,"status":s,"confidence":c}
p={"verified_financials":{"revenue_growth_yoy":i(.22,"PRIMARY_ONLY",.85),"net_margin":i(-.03,"STRONG_AGREEMENT",.97),"operating_margin":i(-.06,"STRONG_AGREEMENT",.97),"free_cash_flow":i(1.3e9,"REVIEW",.72),"operating_cash_flow":i(1.6e9,"STRONG_AGREEMENT",.97),"cash":i(5e9,"PERIOD_MISMATCH",.7),"debt":i(.75e9,"PERIOD_MISMATCH",.7)}}
f=SimpleNamespace(revenue_growth=.22,profit_margin=-.03,operating_margin=-.06,free_cash_flow=1.3e9,operating_cash_flow=1.6e9,total_cash=5e9,total_debt=.75e9)
h=FinancialEngine().analyze(f,p)
assert h.evidence_coverage==100 and h.confidence_adjusted_score!=h.score
p2={"verified_financials":dict(p["verified_financials"])};p2["verified_financials"]["operating_margin"]=i(None,"MISSING",0)
h2=FinancialEngine().analyze(f,p2);assert h2.evidence_coverage<h.evidence_coverage and "operating_margin" in h2.gated_metrics
print("V3.6 confidence-aware financial health: PASS")
print("quality:",h.score,"confidence:",h.evidence_confidence,"coverage:",h.evidence_coverage,"adjusted:",h.confidence_adjusted_score)
