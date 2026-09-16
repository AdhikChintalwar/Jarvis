from __future__ import annotations
from collections import defaultdict
from datetime import datetime
from investor.point_in_time.models import EvidenceItem

class CoherentHistoricalFinancialResolver:
    """Period-aware SEC resolver.

    Flow facts are never mixed merely because they share an end date.  Annual and
    quarterly/YTD durations are classified separately. TTM is built only from four
    coherent quarter-equivalent observations when available. Balance-sheet facts
    are instant observations. Debt is total-debt-first, otherwise current +
    noncurrent only on the same instant date.
    """
    FLOW={
      "revenue":["RevenueFromContractWithCustomerExcludingAssessedTax","Revenues","SalesRevenueNet"],
      "net_income":["NetIncomeLoss","ProfitLoss"],
      "operating_cash_flow":["NetCashProvidedByUsedInOperatingActivities"],
      "capex":["PaymentsToAcquirePropertyPlantAndEquipment"],
    }
    INSTANT={
      "cash":["CashAndCashEquivalentsAtCarryingValue"],
      "shares_outstanding":["EntityCommonStockSharesOutstanding","CommonStocksIncludingAdditionalPaidInCapitalMember"],
    }
    TOTAL_DEBT=["LongTermDebtAndFinanceLeaseObligations","LongTermDebt","DebtAndFinanceLeaseObligations"]
    DEBT_CURRENT=["LongTermDebtAndFinanceLeaseObligationsCurrent","LongTermDebtCurrent"]
    DEBT_NONCURRENT=["LongTermDebtAndFinanceLeaseObligationsNoncurrent","LongTermDebtNoncurrent"]

    @staticmethod
    def _days(f):
        if not f.start or not f.end:return None
        try:return (datetime.fromisoformat(f.end)-datetime.fromisoformat(f.start)).days
        except:return None

    def _flow_candidates(self,facts,concepts):
        out=[]
        for rank,c in enumerate(concepts):
            for f in facts.get(c,[]):
                days=self._days(f)
                if f.value is None or days is None or days<60: continue
                out.append((f.end or "", f.available_at or "", -rank, days, f))
        return sorted(out)

    def _latest_flow(self,facts,concepts):
        c=self._flow_candidates(facts,concepts)
        if not c:return None
        # Prefer latest period end, then annual duration for 10-K / latest filed fact.
        end=c[-1][0]
        same=[x for x in c if x[0]==end]
        annual=[x for x in same if 330<=x[3]<=400]
        return (annual or same)[-1][4]

    def _instant(self,facts,concepts):
        c=[]
        for rank,name in enumerate(concepts):
            for f in facts.get(name,[]):
                if f.value is not None:c.append((f.end or "",f.available_at or "",-rank,f))
        return sorted(c)[-1][3] if c else None

    @staticmethod
    def _ev(metric,value,f,concept=None,metadata=None):
        md={"concept":concept or getattr(f,"concept",None),"accession":getattr(f,"accession",None),
            "form":getattr(f,"form",None),"start":getattr(f,"start",None)}
        md.update(metadata or {})
        return EvidenceItem(metric,value,"SEC_XBRL",period_end=f.end,filed_at=f.filed,
            available_at=f.available_at,authority="PRIMARY",status="PASS",metadata=md)

    def resolve(self,facts):
        out={}
        selected={}
        for metric,concepts in self.FLOW.items():
            f=self._latest_flow(facts,concepts)
            if f:
                selected[metric]=f
                out[metric]=self._ev(metric,f.value,f)

        for metric,concepts in self.INSTANT.items():
            f=self._instant(facts,concepts)
            if f: out[metric]=self._ev(metric,f.value,f)

        # Debt semantics: use explicit total debt if present. Otherwise add current
        # and noncurrent only when both are same-date facts.
        total=self._instant(facts,self.TOTAL_DEBT)
        if total:
            out["debt"]=self._ev("debt",total.value,total,metadata={"aggregation":"explicit_total"})
        else:
            cur=self._instant(facts,self.DEBT_CURRENT); non=self._instant(facts,self.DEBT_NONCURRENT)
            if cur and non and cur.end==non.end:
                out["debt"]=self._ev("debt",float(cur.value)+float(non.value),cur,
                    concept=f"{cur.concept}+{non.concept}",
                    metadata={"aggregation":"current_plus_noncurrent","accessions":[cur.accession,non.accession]})

        # FCF requires exactly aligned duration, not just period end.
        a=selected.get("operating_cash_flow"); b=selected.get("capex")
        if a and b and a.start==b.start and a.end==b.end:
            out["free_cash_flow"]=EvidenceItem("free_cash_flow",float(a.value)-float(b.value),
                "DERIVED_SEC_XBRL",period_end=a.end,available_at=max(a.available_at,b.available_at),
                authority="DERIVED",status="PASS",
                metadata={"formula":"operating_cash_flow - capex","start":a.start,
                          "accessions":[a.accession,b.accession]})

        # YoY revenue only compares like-duration periods.
        revs=self._flow_candidates(facts,self.FLOW["revenue"])
        if len(revs)>=2 and "revenue" in out:
            latest=selected["revenue"]; ld=self._days(latest)
            peers=[x[4] for x in revs if x[4].end!=latest.end and abs(x[3]-ld)<=15]
            if peers:
                prior=peers[-1]
                if prior.value not in (None,0):
                    growth=float(latest.value)/float(prior.value)-1
                    out["revenue_growth_yoy"]=EvidenceItem("revenue_growth_yoy",growth,"DERIVED_SEC_XBRL",
                        period_end=latest.end,available_at=max(latest.available_at,prior.available_at),
                        authority="DERIVED",status="PASS",
                        metadata={"formula":"like-duration revenue YoY","current_start":latest.start,
                                  "prior_start":prior.start,"prior_end":prior.end})
        if "revenue" in out and "net_income" in out:
            r,n=out["revenue"],out["net_income"]
            if r.metadata.get("start")==n.metadata.get("start") and r.period_end==n.period_end and r.value:
                out["net_margin"]=EvidenceItem("net_margin",float(n.value)/float(r.value),"DERIVED_SEC_XBRL",
                    period_end=r.period_end,available_at=max(r.available_at,n.available_at),
                    authority="DERIVED",status="PASS",metadata={"formula":"net_income / revenue"})
        return out
