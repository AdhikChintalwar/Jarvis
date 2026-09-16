import sys, types
for mod in ("yfinance","openai"):
    if mod not in sys.modules: sys.modules[mod]=types.ModuleType(mod)
sys.modules["yfinance"].download=lambda *a,**k:None
sys.modules["yfinance"].Ticker=type("Ticker",(),{"__init__":lambda self,*a,**k:None,"info":{},"news":[]})
sys.modules["openai"].OpenAI=type("OpenAI",(),{"__init__":lambda self,*a,**k:None})

from investor.committee.committee import NemotronInvestmentCommittee
from investor.committee.models import CandidateIntelligence,AnalystVerdict,CriticVerdict

class Fake:
    def __init__(self): self.calls=[]
    def reason_json(self,**k):
        self.calls.append((k["task_name"],k["enable_thinking"]))
        if k["task_name"]=="investment_deliberation_deep_v4_5":
            return {"deliberations":[{"symbol":"CRWD","bull_score":60,"bear_score":80,"synthesis_score":45,"confidence":80,
            "bull_claims":[{"claim_id":"B1","statement":"Financial health score is 62.0.","type":"FACT","category":"STRENGTH","evidence_ids":["financial_health.score"],"confidence":90}],
            "bear_claims":[{"claim_id":"R1","statement":"Unified risk level is VERY_HIGH.","type":"FACT","category":"RISK","evidence_ids":["unified_risk.risk_level"],"confidence":99}],
            "contradictions":["Risk and growth pull in opposite directions."],
            "unresolved_questions":["Future profitability is unknown."]}]}
        assert k["task_name"]=="investment_committee_deep_v4_5"
        assert k["enable_thinking"] is True
        assert "validated_deliberation" in k["payload"]["candidates"][0]
        return {"rankings":[{"symbol":"CRWD","rank":1,"committee_score":95,"decision":"TOP_CANDIDATE","confidence":95,
        "claims":[{"claim_id":"F1","statement":"Unified risk level is VERY_HIGH.","type":"FACT","category":"RISK","evidence_ids":["unified_risk.risk_level"],"confidence":95}]}]}

ev={"financial_health":{"score":62,"confidence_adjusted_score":62,"evidence_confidence":84,"evidence_coverage":100},
"accounting_quality":{"score":68,"confidence":62,"coverage":75},"valuation":{"score":14,"confidence":46,"coverage":62.5},
"event_intelligence":{"score":50,"confidence":50,"coverage":75},"macro_regime":{"score":40,"confidence":86,"coverage":100},
"advanced_market":{"score":50,"confidence":68,"coverage":100},
"unified_risk":{"risk_score":80,"risk_level":"VERY_HIGH","confidence":66,"coverage":100,
"hard_overrides":["Extreme realized-volatility hard override triggered."]}}
c=CandidateIntelligence(symbol="CRWD",scanner_score=80,flow_score=80,evidence=ev,
analyst=AnalystVerdict(symbol="CRWD",decision="CANDIDATE",conviction=80,evidence_quality=90),
critic=CriticVerdict(symbol="CRWD",thesis_survives=True,adjusted_conviction=75),final_candidate_score=80,passed_gate=True)
f=Fake(); r=NemotronInvestmentCommittee(f).rank([c],deep_review=True)["rankings"][0]
assert f.calls==[("investment_deliberation_deep_v4_5",True),("investment_committee_deep_v4_5",True)],f.calls
assert r["decision"]=="WATCH" and r["maximum_decision"]=="WATCH"
assert r["governance_status"]=="RISK_CONSTRAINED"
print("V4.5 deep-investment-reasoning contract: PASS")
print("calls:",f.calls)
print("decision:",r["decision"],"max:",r["maximum_decision"])
print("final:",r["committee_score"],"deterministic:",r["deterministic_score"],"llm:",r["llm_score"])
print("integrity:",r["integrity_score"],"authority:",r["evidence_authority"])
