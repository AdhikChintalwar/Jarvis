import argparse
from investor import StockAnalyzer, BabyInvestmentSystem
from investor.providers.yahoo_provider import YahooFinanceProvider

p=argparse.ArgumentParser()
p.add_argument("symbols",nargs="*",default=["AAPL","SLDE","CRWD"])
p.add_argument("--account",type=float)
a=p.parse_args()

provider=YahooFinanceProvider()
system=BabyInvestmentSystem()
print("="*108)
print("BABY INVESTOR V4.8 — INDEPENDENT ALPHA VANTAGE CROSS-SOURCE VALIDATION")
print("="*108)

for symbol in a.symbols:
    print("\n"+"-"*108);print(symbol)
    report=StockAnalyzer().analyze(symbol)
    h=provider.get_history(symbol,"1y","1d")
    r=system.evaluate(report,h,account_size=a.account)
    d=r.decision;v=r.validation;t=r.trade_plan;e=r.external_provider or {}
    print("Decision:",d["score"],d["research_state"],"| confidence",d["evidence_confidence"],"| coverage",d["evidence_coverage"])
    print("Risk constraints:",d["constraints"])
    print("AI authority:",r.ai_scoring_authority,"| execution:",r.execution_authority)
    print("External provider:",e.get("provider"),"|",e.get("status"),"| independent",e.get("independent"))
    print("External as-of: market",e.get("market_as_of"),"| financial",e.get("financial_as_of"))
    for w in e.get("warnings") or []: print("  PROVIDER WARNING:",w)
    print("Validation:",v["status"],v["score"],"| coverage",v["coverage"],"P/R/F/U",
          v["checks_passed"],v["checks_review"],v["checks_failed"],v["checks_unknown"])
    for c in v["checks"]:
        print(f'  {c["status"]:7} {c["name"]:<34} obs={c["observed"]} ref={c["reference"]} source={c["source"]} authority={c["authority"]}')
    print("Current:",t["current_price"],"| as-of",t["market_data_as_of"])
    print("Current setup:",t["current_setup"]["status"],"-",t["current_setup"]["reason"])
    print("Valuation:",t["valuation_context"],"| risk:",t["risk_level"],"| hard override:",t["hard_risk_override"])

    assert r.ai_scoring_authority==0.0 and r.execution_authority=="NONE"
    if e.get("status")=="ACTIVE":
        assert e.get("independent") is True
        assert any(c["name"].startswith("external.") for c in v["checks"])
    if t["risk_level"] in {"VERY_HIGH","EXTREME"} or t["hard_risk_override"]:
        assert t["current_setup"]["status"]=="WAIT_RISK_CONSTRAINED"

print("\nRESULT: PASS")
