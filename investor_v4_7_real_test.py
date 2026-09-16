import argparse
from investor import StockAnalyzer, BabyInvestmentSystem
from investor.providers.yahoo_provider import YahooFinanceProvider
p=argparse.ArgumentParser();p.add_argument("symbols",nargs="*",default=["AAPL","SLDE","CRWD"]);p.add_argument("--account",type=float);a=p.parse_args()
provider=YahooFinanceProvider();system=BabyInvestmentSystem()
print("="*100);print("BABY INVESTOR V4.7 — DECISION + VALIDATION + TRADE RESEARCH FOUNDATION");print("="*100)
for symbol in a.symbols:
 print("\n"+"-"*100);print(symbol)
 report=StockAnalyzer().analyze(symbol);h=provider.get_history(symbol,"1y","1d");r=system.evaluate(report,h,account_size=a.account)
 d=r.decision;v=r.validation;t=r.trade_plan
 print("Decision:",d["score"],d["research_state"],"| confidence",d["evidence_confidence"],"| coverage",d["evidence_coverage"])
 print("Risk constraints:",d["constraints"]);print("AI authority:",r.ai_scoring_authority,"| execution:",r.execution_authority)
 print("Validation:",v["status"],v["score"],"P/R/F/U",v["checks_passed"],v["checks_review"],v["checks_failed"],v["checks_unknown"])
 for c in v["checks"]: print(f'  {c["status"]:7} {c["name"]:<32} obs={c["observed"]} ref={c["reference"]} authority={c.get("authority")}')
 print("Current:",t["current_price"],"| as-of",t["market_data_as_of"],"| rows",t["history_observations"])
 print("Current setup:",t["current_setup"]["status"],"-",t["current_setup"]["reason"])
 pb=t["pullback"];bo=t["breakout"]
 print("Pullback:",pb["status"],"entry",pb["entry_low"],"-",pb["entry_high"],"stop",pb["invalidation"],"targets",pb["target_1"],pb["target_2"],"R:R",pb["risk_reward_1"],pb["risk_reward_2"])
 print("Breakout:",bo["status"],"trigger",bo["trigger"],"stop",bo["invalidation"],"targets",bo["target_1"],bo["target_2"])
 print("Valuation:",t["valuation_context"],"| unified risk:",t["risk_level"],"| hard override:",t["hard_risk_override"])
 for n in t["notes"]:print("  NOTE:",n)
 # Semantic invariants
 if pb["planned_entry"] is not None:
  assert pb["invalidation"] < pb["planned_entry"]
  if pb["target_1"] is not None: assert pb["target_1"] > pb["planned_entry"]
 if bo["trigger"] is not None:
  assert bo["invalidation"] < bo["trigger"]
  assert bo["target_1"] > bo["trigger"] and bo["target_2"] > bo["trigger"]
 if t["risk_level"] in {"VERY_HIGH","EXTREME"} or t["hard_risk_override"]:
  assert t["current_setup"]["status"]=="WAIT_RISK_CONSTRAINED"
 if a.account is None: assert t["position"] is None
print("\nRESULT: PASS")
