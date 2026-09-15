from __future__ import annotations
from dataclasses import dataclass
from typing import Any,Iterable

CANONICAL_FINANCIAL_EVIDENCE_METRICS = (
    "revenue_growth_yoy",
    "net_margin",
    "operating_margin",
    "free_cash_flow",
    "operating_cash_flow",
    "cash",
    "debt",
)

GATED_STATUSES={"MATERIAL_DISAGREEMENT","MISSING"}
STATUS_AUTHORITY={"STRONG_AGREEMENT":.97,"AGREEMENT":.94,"MINOR_DIFFERENCE":.88,"PRIMARY_ONLY":.85,"DEFINITION_MISMATCH":.78,"DEFINITION_UNVERIFIED":.65,"REVIEW":.72,"PERIOD_MISMATCH":.70,"SECONDARY_ONLY":.55,"MATERIAL_DISAGREEMENT":0.,"MISSING":0.}
@dataclass(frozen=True)
class MetricEvidence:
    name:str;value:Any;status:str;confidence:float;authority:float;available:bool;gated:bool;period:str|None=None;source:str|None=None
class FinancialEvidenceContext:
    def __init__(self,primary_financial:dict|None=None):
        self.verified=(primary_financial or {}).get("verified_financials") or {}
    def metric(self,name):
        x=self.verified.get(name) or {};v=x.get("value");s=str(x.get("status") or "MISSING").upper()
        try:c=float(x.get("confidence") or 0)
        except (TypeError,ValueError):c=0.
        a=max(0.,min(1.,min(c,STATUS_AUTHORITY.get(s,c))));g=s in GATED_STATUSES or v is None
        if g:a=0.
        return MetricEvidence(name,v,s,c,a,v is not None and not g,g,x.get("period"),x.get("source"))
    def summarize(self,names:Iterable[str]):
        ms=[self.metric(n) for n in names]
        if not ms:return {"confidence":0.,"coverage":0.,"available":[],"gated":[]}
        av=[m for m in ms if m.available]
        return {"confidence":sum(m.authority for m in av)/len(ms),"coverage":len(av)/len(ms),"available":[m.name for m in av],"gated":[m.name for m in ms if m.gated]}
