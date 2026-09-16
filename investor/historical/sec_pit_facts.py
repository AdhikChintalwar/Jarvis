from dataclasses import dataclass
from typing import Optional
from .sec_history import SECHistoricalFilings

@dataclass
class HistoricalFact:
    concept:str; value:float; unit:str; start:Optional[str]; end:Optional[str]
    filed:str; form:str; accession:str; frame:Optional[str]; source:str="SEC_XBRL"
    available_at:Optional[str]=None

class SECPointInTimeFacts:
    """Filters Company Facts by the filing that made each fact public.

    Company Facts may contain later restatements. A fact is usable historically
    only when its accession/filed timestamp was available by the simulated date.
    """
    def __init__(self,sec:SECHistoricalFilings):
        self.sec=sec

    def companyfacts(self,cik):
        c=self.sec.cik10(cik)
        return self.sec._get(f"{self.sec.BASE}/api/xbrl/companyfacts/CIK{c}.json").json()

    def facts_as_of(self,cik,as_of,taxonomy="us-gaap",forms=("10-K","10-Q")):
        available={f["accessionNumber"]:f for f in self.sec.filings_available(cik,as_of,forms)}
        data=self.companyfacts(cik)
        out={}
        for concept,node in data.get("facts",{}).get(taxonomy,{}).items():
            vals=[]
            for unit,items in node.get("units",{}).items():
                for x in items:
                    acc=x.get("accn")
                    if acc not in available: continue
                    vals.append(HistoricalFact(
                        concept=concept,value=x.get("val"),unit=unit,start=x.get("start"),
                        end=x.get("end"),filed=x.get("filed"),form=x.get("form"),
                        accession=acc,frame=x.get("frame"),
                        available_at=available[acc].get("available_at")))
            if vals: out[concept]=vals
        return out
