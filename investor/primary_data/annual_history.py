from __future__ import annotations
from datetime import date

class AnnualFinancialHistoryBuilder:
    MAX_END_GAP_DAYS = 45
    METRICS = ("revenue","operating_income","net_income","operating_cash_flow","capex","weighted_average_diluted_shares")

    def build(self, statements: dict, max_periods: int = 5) -> dict:
        revenue = statements.get("revenue")
        if not revenue or not revenue.calculation_allowed:
            return {"periods":[],"coverage":0.0,"warnings":["Revenue history unavailable."]}
        anchors = self._unique_annual(revenue.annual)[-max_periods:]
        rows=[]
        for rev in anchors:
            row={"period_end":rev.end,"period_start":rev.start,"revenue":rev.value}
            for metric in self.METRICS[1:]:
                row[metric]=self._near_period_value(statements.get(metric),rev.end)
            ocf,capex=row.get("operating_cash_flow"),row.get("capex")
            row["free_cash_flow"]=ocf-abs(capex) if ocf is not None and capex is not None else None
            rv=row.get("revenue")
            for out,num in (("operating_margin","operating_income"),("net_margin","net_income"),
                            ("operating_cash_flow_margin","operating_cash_flow"),("free_cash_flow_margin","free_cash_flow")):
                row[out]=row.get(num)/rv if rv not in (None,0) and row.get(num) is not None else None
            rows.append(row)
        expected=len(rows)*6
        known=sum(row.get(k) is not None for row in rows for k in self.METRICS)
        return {"periods":rows,"coverage":round(known/expected,4) if expected else 0.0,"warnings":[]}

    @staticmethod
    def _unique_annual(rows):
        by_end={}
        for fact in rows:
            if fact.value is None or not fact.end: continue
            cur=by_end.get(fact.end)
            if cur is None or (fact.filed or "")>(cur.filed or ""): by_end[fact.end]=fact
        return [by_end[k] for k in sorted(by_end)]

    def _near_period_value(self, series, anchor_end):
        if not series or not series.calculation_allowed: return None
        try: anchor=date.fromisoformat(anchor_end)
        except ValueError: return None
        candidates=[]
        for fact in self._unique_annual(series.annual):
            try: gap=abs((date.fromisoformat(fact.end)-anchor).days)
            except ValueError: continue
            if gap<=self.MAX_END_GAP_DAYS: candidates.append((gap,fact))
        return min(candidates,key=lambda x:x[0])[1].value if candidates else None
