from __future__ import annotations
from dataclasses import dataclass,field
from typing import Optional
from investor.financial_evidence import FinancialEvidenceContext, CANONICAL_FINANCIAL_EVIDENCE_METRICS
@dataclass
class FinancialHealth:
    score:float;revenue_growth_score:float;profitability_score:float;cash_flow_score:float;balance_sheet_score:float
    cash_to_debt_ratio:Optional[float];cash_runway_years:Optional[float]
    evidence_confidence:float=0.;evidence_coverage:float=0.;confidence_adjusted_score:float=50.
    gated_metrics:list[str]=field(default_factory=list);available_metrics:list[str]=field(default_factory=list)
    warnings:list[str]=field(default_factory=list);strengths:list[str]=field(default_factory=list)
class FinancialEngine:
    METRICS=CANONICAL_FINANCIAL_EVIDENCE_METRICS
    def analyze(self,f,primary_financial=None):
        g=self._g(f.revenue_growth);p=self._p(f.profit_margin,f.operating_margin);c=self._c(f.free_cash_flow,f.operating_cash_flow);b=self._b(f.total_cash,f.total_debt)
        groups=[(g,.25,f.revenue_growth is not None),(p,.30,f.profit_margin is not None or f.operating_margin is not None),(c,.25,f.free_cash_flow is not None or f.operating_cash_flow is not None),(b,.20,f.total_cash is not None and f.total_debt is not None)]
        u=[(s,w) for s,w,ok in groups if ok];q=sum(s*w for s,w in u)/sum(w for _,w in u) if u else 50.
        sm=FinancialEvidenceContext(primary_financial).summarize(self.METRICS) if primary_financial else {"confidence":0.,"coverage":0.,"available":[],"gated":[]}
        cf=sm["confidence"];adj=50+(q-50)*cf if primary_financial else q;wa=[];st=[]
        if sm["gated"]:wa.append("Evidence-gated financial metrics: "+", ".join(sm["gated"])+".")
        if primary_financial and sm["coverage"]<.75:wa.append(f"Financial evidence coverage is {sm['coverage']:.0%}; missing evidence reduces conviction, not company quality.")
        r=None
        if f.total_cash is not None and f.total_debt is not None:r=f.total_cash/f.total_debt if f.total_debt>0 else (float("inf") if f.total_cash>0 else None)
        run=self._run(f.total_cash,f.free_cash_flow)
        if f.revenue_growth is not None:
            if f.revenue_growth>.20:st.append("Revenue growth exceeds 20%.")
            elif f.revenue_growth<0:wa.append("Revenue is declining.")
        if f.profit_margin is not None:
            if f.profit_margin>.15:st.append("Profit margins are strong.")
            elif f.profit_margin<0:wa.append("Company is currently unprofitable.")
        if f.free_cash_flow is not None:
            (st if f.free_cash_flow>0 else wa).append("Company generates positive free cash flow." if f.free_cash_flow>0 else "Company has negative free cash flow.")
        return FinancialHealth(round(q,2),round(g,2),round(p,2),round(c,2),round(b,2),r,run,round(cf*100,2),round(sm["coverage"]*100,2),round(adj,2),sm["gated"],sm["available"],wa,st)
    def _g(self,x):
        if x is None:return 50
        return 95 if x>=.5 else 85 if x>=.25 else 70 if x>=.1 else 55 if x>=0 else 40 if x>=-.1 else 20
    def _p(self,p,o):
        v=[]
        if p is not None:v.append(95 if p>=.25 else 80 if p>=.15 else 65 if p>=.05 else 55 if p>=0 else 25)
        if o is not None:v.append(90 if o>=.2 else 75 if o>=.1 else 55 if o>=0 else 30)
        return sum(v)/len(v) if v else 50
    def _c(self,f,o):
        v=[]
        if f is not None:v.append(75 if f>0 else 30)
        if o is not None:v.append(70 if o>0 else 35)
        return sum(v)/len(v) if v else 50
    def _b(self,c,d):
        if c is None or d is None:return 50
        if d<=0:return 90 if c>0 else 60
        r=c/d;return 90 if r>=2 else 80 if r>=1 else 60 if r>=.5 else 40 if r>=.25 else 20
    def _run(self,c,f):
        return None if c is None or f is None or f>=0 else c/abs(f)
