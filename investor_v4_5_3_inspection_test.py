import sys, types
if "yfinance" not in sys.modules:
    yf=types.ModuleType("yfinance"); yf.download=lambda *a,**k:None
    yf.Ticker=type("Ticker",(),{"__init__":lambda self,*a,**k:None,"info":{},"news":[]})
    sys.modules["yfinance"]=yf
if "openai" not in sys.modules:
    op=types.ModuleType("openai");op.OpenAI=object;sys.modules["openai"]=op

from investor.committee.committee import NemotronInvestmentCommittee
from investor.committee.models import CandidateIntelligence,AnalystVerdict,CriticVerdict

class Fake:
    def reason_json(self, **k):
        if k["task_name"]=="investment_deliberation_deep_v4_5":
            return {"deliberations":[{
                "symbol":"CRWD","bull_score":60,"bear_score":80,
                "synthesis_score":45,"confidence":80,
                "bull_claims":[{"claim_id":"B1","statement":"Financial health score is 62.0.","type":"FACT","category":"STRENGTH","evidence_ids":["financial_health.score"],"confidence":90}],
                "bear_claims":[{"claim_id":"R1","statement":"Unified risk level is VERY_HIGH.","type":"FACT","category":"RISK","evidence_ids":["unified_risk.risk_level"],"confidence":99}],
                "contradictions":[],
                "unresolved_questions":["Future profitability is unknown."]
            }]}
        return {"rankings":[{
            "symbol":"CRWD","rank":1,"committee_score":95,
            "decision":"TOP_CANDIDATE","confidence":95,
            "claims":[{"claim_id":"F1","statement":"Unified risk level is VERY_HIGH.","type":"FACT","category":"RISK","evidence_ids":["unified_risk.risk_level"],"confidence":95}]
        }]}

ev={"financial_health":{"score":62,"confidence_adjusted_score":62,"evidence_confidence":84,"evidence_coverage":100},
"accounting_quality":{"score":68,"confidence":62,"coverage":75},"valuation":{"score":14,"confidence":46,"coverage":62.5},
"event_intelligence":{"score":50,"confidence":50,"coverage":75},"macro_regime":{"score":40,"confidence":86,"coverage":100},
"advanced_market":{"score":50,"confidence":68,"coverage":100},
"unified_risk":{"risk_score":80,"risk_level":"VERY_HIGH","confidence":66,"coverage":100,
"hard_overrides":["Extreme realized-volatility hard override triggered."]}}

c=CandidateIntelligence(symbol="CRWD",scanner_score=80,flow_score=80,evidence=ev,
analyst=AnalystVerdict(symbol="CRWD",decision="CANDIDATE",conviction=80,evidence_quality=90),
critic=CriticVerdict(symbol="CRWD",thesis_survives=True,adjusted_conviction=75),
final_candidate_score=80,passed_gate=True)

result=NemotronInvestmentCommittee(Fake()).rank([c],deep_review=True)
assert "deep_deliberation" in result
assert "CRWD" in result["deep_deliberation"]
d=result["deep_deliberation"]["CRWD"]
assert d["bull_score"]==60 and d["bear_score"]==80
assert d["integrity_score"]>=0
r=result["rankings"][0]
assert r["decision"]=="WATCH"
print("V4.5.3 reasoning-inspection contract: PASS")
print("deep deliberation exported: PASS")
print("risk governance preserved: PASS")
