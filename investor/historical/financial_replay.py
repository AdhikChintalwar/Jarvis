from investor.point_in_time.models import EvidenceItem

class HistoricalFinancialResolver:
    CONCEPTS={
      "revenue":["RevenueFromContractWithCustomerExcludingAssessedTax","Revenues","SalesRevenueNet"],
      "net_income":["NetIncomeLoss","ProfitLoss"],
      "operating_cash_flow":["NetCashProvidedByUsedInOperatingActivities"],
      "capex":["PaymentsToAcquirePropertyPlantAndEquipment"],
      "cash":["CashAndCashEquivalentsAtCarryingValue","CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"],
      "debt":["LongTermDebtAndFinanceLeaseObligationsCurrent","LongTermDebtCurrent","LongTermDebtNoncurrent"],
    }
    def resolve(self,facts):
        out={}
        for metric,concepts in self.CONCEPTS.items():
            candidates=[]
            for rank,c in enumerate(concepts):
                for f in facts.get(c,[]):
                    if f.value is None: continue
                    candidates.append((f.end or "",-rank,f))
            if not candidates: continue
            f=sorted(candidates,key=lambda x:(x[0],x[1]))[-1][2]
            out[metric]=EvidenceItem(metric,f.value,"SEC_XBRL",period_end=f.end,
                filed_at=f.filed,available_at=f.available_at,authority="PRIMARY",
                status="PASS",metadata={"concept":f.concept,"accession":f.accession,"form":f.form})
        # deterministic FCF only when comparable OCF/capex exist
        if "operating_cash_flow" in out and "capex" in out:
            a,b=out["operating_cash_flow"],out["capex"]
            if a.period_end==b.period_end:
                out["free_cash_flow"]=EvidenceItem("free_cash_flow",a.value-b.value,
                    "DERIVED_SEC_XBRL",period_end=a.period_end,
                    available_at=max(a.available_at,b.available_at),authority="DERIVED",
                    status="PASS",metadata={"formula":"operating_cash_flow - capex"})
        return out
