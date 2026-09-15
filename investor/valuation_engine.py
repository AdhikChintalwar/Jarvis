from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import math
from investor.financial_evidence import FinancialEvidenceContext

@dataclass
class ValuationReport:
    score: float = 50.0
    confidence: float = 0.0
    coverage: float = 0.0
    absolute_valuation_score: float = 50.0
    growth_adjusted_score: float = 50.0
    profitability_state: str = "UNKNOWN"
    fcf_state: str = "UNKNOWN"
    market_data_as_of: Optional[str] = None
    financial_period: Optional[str] = None
    market_cap: Optional[float] = None
    enterprise_value: Optional[float] = None
    trailing_pe: Optional[float] = None
    price_to_sales: Optional[float] = None
    ev_to_sales: Optional[float] = None
    price_to_fcf: Optional[float] = None
    ev_to_fcf: Optional[float] = None
    earnings_yield: Optional[float] = None
    fcf_yield: Optional[float] = None
    forward_pe: Optional[float] = None
    growth_adjusted_pe: Optional[float] = None
    positive_signals: list[str] = field(default_factory=list)
    red_flags: list[str] = field(default_factory=list)
    unknowns: list[str] = field(default_factory=list)
    evidence: dict = field(default_factory=dict)

class ValuationEngine:
    """
    V3.8 deterministic valuation.

    Current market price/cap are market facts; statement denominators come from
    verified primary financials. Forward P/E remains secondary/prototype evidence
    and is never allowed to override primary trailing valuation.
    """

    SIGNALS=("trailing_pe","price_to_sales","ev_to_sales","price_to_fcf",
             "ev_to_fcf","earnings_yield","fcf_yield","growth_adjusted_pe")

    def analyze(self, market, fundamentals, primary_financial=None):
        ev=FinancialEvidenceContext(primary_financial)
        pos=[]; red=[]; unk=[]; evidence={}; contributions=[]

        market_cap=self._positive(getattr(fundamentals,"market_cap",None))
        if market_cap is None:
            shares=self._positive(getattr(fundamentals,"shares_outstanding",None))
            price=self._positive(getattr(market,"current_price",None))
            market_cap=shares*price if shares and price else None

        revenue=ev.metric("revenue"); ni=ev.metric("net_income")
        fcf=ev.metric("free_cash_flow"); cash=ev.metric("cash"); debt=ev.metric("debt")
        growth=ev.metric("revenue_growth_yoy")

        enterprise_value=None
        if market_cap is not None and cash.available and debt.available:
            enterprise_value=market_cap+debt.value-cash.value

        profitability_state = (
            "PROFITABLE" if ni.available and ni.value is not None and ni.value > 0
            else "LOSS_MAKING" if ni.available and ni.value is not None and ni.value <= 0
            else "UNKNOWN"
        )
        fcf_state = (
            "FCF_POSITIVE" if fcf.available and fcf.value is not None and fcf.value > 0
            else "FCF_NEGATIVE" if fcf.available and fcf.value is not None and fcf.value <= 0
            else "UNKNOWN"
        )

        # Earnings/FCF valuation multiples are meaningful only with positive denominators.
        pe=self._multiple(market_cap,ni.value if profitability_state=="PROFITABLE" else None)
        ps=self._multiple(market_cap,revenue.value if revenue.available else None)
        evs=self._multiple(enterprise_value,revenue.value if revenue.available else None)
        pfcf=self._multiple(market_cap,fcf.value if fcf_state=="FCF_POSITIVE" else None)
        evfcf=self._multiple(enterprise_value,fcf.value if fcf_state=="FCF_POSITIVE" else None)
        ey=self._yield(ni.value if profitability_state=="PROFITABLE" else None,market_cap)
        fy=self._yield(fcf.value if fcf_state=="FCF_POSITIVE" else None,market_cap)

        # PEG-like diagnostic uses verified trailing P/E and verified revenue growth.
        gap=None
        if pe is not None and growth.available and growth.value is not None and growth.value>0:
            growth_pct=growth.value*100.0
            gap=pe/growth_pct if growth_pct else None

        forward_pe=self._positive(getattr(fundamentals,"forward_pe",None))

        market_data_as_of = self._market_date(market)
        financial_period = self._financial_period(primary_financial)

        def register(name,value,authority,source):
            evidence[name]={"available":value is not None,"authority":authority if value is not None else 0.0,"source":source}
            if value is None: unk.append(name)

        mkt_auth=.80 if market_cap is not None else 0.
        register("trailing_pe",pe,min(mkt_auth,ni.authority) if ni.available else 0.,"market_cap + verified net_income")
        register("price_to_sales",ps,min(mkt_auth,revenue.authority) if revenue.available else 0.,"market_cap + verified revenue")
        bs_auth=min(cash.authority,debt.authority) if cash.available and debt.available else 0.
        register("ev_to_sales",evs,min(mkt_auth,bs_auth,revenue.authority) if revenue.available and bs_auth else 0.,"derived EV + verified revenue")
        register("price_to_fcf",pfcf,min(mkt_auth,fcf.authority) if fcf.available else 0.,"market_cap + verified FCF")
        register("ev_to_fcf",evfcf,min(mkt_auth,bs_auth,fcf.authority) if fcf.available and bs_auth else 0.,"derived EV + verified FCF")
        register("earnings_yield",ey,min(mkt_auth,ni.authority) if ni.available else 0.,"verified net_income / market_cap")
        register("fcf_yield",fy,min(mkt_auth,fcf.authority) if fcf.available else 0.,"verified FCF / market_cap")
        register("growth_adjusted_pe",gap,min(mkt_auth,ni.authority,growth.authority) if ni.available and growth.available else 0.,"trailing PE / verified revenue growth %")
        evidence["forward_pe"]={"available":forward_pe is not None,"authority":.45 if forward_pe is not None else 0.,"source":"secondary/prototype market provider"}
        evidence["profitability_state"]={"value":profitability_state,"source":"verified net_income"}
        evidence["fcf_state"]={"value":fcf_state,"source":"verified free_cash_flow"}
        evidence["valuation_basis"]={
            "market_data_as_of":market_data_as_of,
            "financial_period":financial_period,
            "description":"Current market valuation using latest verified financial-period denominators.",
        }
        if profitability_state=="LOSS_MAKING":
            red.append("Company is loss-making; trailing earnings valuation is not meaningful.")
        if fcf_state=="FCF_NEGATIVE":
            red.append("Free cash flow is non-positive; FCF valuation multiples are not meaningful.")

        # Broad deterministic bands. These are heuristics, not intrinsic-value claims.
        absolute_contributions=[]
        growth_contributions=[]
        self._low_multiple("trailing P/E",pe,evidence["trailing_pe"]["authority"],15,25,40,absolute_contributions,pos,red)
        self._low_multiple("price/sales",ps,evidence["price_to_sales"]["authority"],2,5,10,absolute_contributions,pos,red)
        self._low_multiple("EV/sales",evs,evidence["ev_to_sales"]["authority"],2,5,10,absolute_contributions,pos,red)
        self._low_multiple("price/FCF",pfcf,evidence["price_to_fcf"]["authority"],15,25,40,absolute_contributions,pos,red)
        self._low_multiple("EV/FCF",evfcf,evidence["ev_to_fcf"]["authority"],15,25,40,absolute_contributions,pos,red)

        if fy is not None:
            a=evidence["fcf_yield"]["authority"]
            if fy>=.06: absolute_contributions.append((10,a));pos.append("Free-cash-flow yield is at least 6%.")
            elif fy>=.04: absolute_contributions.append((5,a))
            elif fy<.02: absolute_contributions.append((-9,a));red.append("Free-cash-flow yield is below 2%.")
        if ey is not None:
            a=evidence["earnings_yield"]["authority"]
            if ey>=.06: absolute_contributions.append((8,a));pos.append("Earnings yield is at least 6%.")
            elif ey<.02: absolute_contributions.append((-7,a));red.append("Earnings yield is below 2%.")
        if gap is not None:
            a=evidence["growth_adjusted_pe"]["authority"]
            if gap<=1.0: growth_contributions.append((7,a));pos.append("Trailing P/E is low relative to verified revenue growth.")
            elif gap>=3.0: growth_contributions.append((-7,a));red.append("Trailing P/E is high relative to verified revenue growth.")

        available=sum(bool(evidence[n]["available"]) for n in self.SIGNALS)
        authorities=[evidence[n]["authority"] for n in self.SIGNALS]
        coverage=available/len(self.SIGNALS)
        confidence=sum(authorities)/len(self.SIGNALS)

        absolute_score=self._calibrated_score(absolute_contributions)
        growth_score=self._calibrated_score(growth_contributions)

        # Absolute valuation is primary. Growth adjustment is a secondary modifier,
        # not permission for extreme multiples to become "cheap."
        if gap is None:
            score=absolute_score
        else:
            score=max(0,min(100,absolute_score*0.80 + growth_score*0.20))

        return ValuationReport(
            score=round(score,2),confidence=round(confidence*100,2),coverage=round(coverage*100,2),
            absolute_valuation_score=round(absolute_score,2),
            growth_adjusted_score=round(growth_score,2),
            profitability_state=profitability_state,fcf_state=fcf_state,
            market_data_as_of=market_data_as_of,financial_period=financial_period,
            market_cap=self._r(market_cap),enterprise_value=self._r(enterprise_value),
            trailing_pe=self._r(pe),price_to_sales=self._r(ps),ev_to_sales=self._r(evs),
            price_to_fcf=self._r(pfcf),ev_to_fcf=self._r(evfcf),
            earnings_yield=self._r(ey),fcf_yield=self._r(fy),forward_pe=self._r(forward_pe),
            growth_adjusted_pe=self._r(gap),positive_signals=pos,red_flags=red,unknowns=unk,evidence=evidence,
        )

    @staticmethod
    def _low_multiple(label,value,a,cheap,normal,expensive,con,pos,red):
        if value is None or not a:return
        if value<=cheap:con.append((8,a));pos.append(f"{label} is in a relatively low heuristic band.")
        elif value<=normal:con.append((3,a))
        elif value>=expensive:con.append((-10,a));red.append(f"{label} is in a high heuristic band.")
        else:con.append((-4,a))
    @staticmethod
    def _calibrated_score(contributions):
        raw=sum(delta*a for delta,a in contributions)
        calibrated=raw if raw<=0 else 50*(1-math.exp(-raw/50))
        return max(0,min(100,50+calibrated))

    @staticmethod
    def _market_date(market):
        for name in ("as_of","as_of_date","market_date","date","timestamp"):
            value=getattr(market,name,None)
            if value is not None:
                return str(value)
        return None

    @staticmethod
    def _financial_period(primary_financial):
        if not primary_financial:
            return None
        verified=primary_financial.get("verified_financials",{})
        periods=[]
        for name in ("revenue","net_income","free_cash_flow"):
            metric=verified.get(name,{}) or {}
            p=metric.get("period")
            if p: periods.append(str(p))
        return periods[0] if periods and len(set(periods))==1 else ("mixed:" + ",".join(sorted(set(periods))) if periods else None)

    @staticmethod
    def _positive(v):
        return v if isinstance(v,(int,float)) and math.isfinite(v) and v>0 else None
    @staticmethod
    def _multiple(n,d):
        return n/d if n is not None and d is not None and d>0 else None
    @staticmethod
    def _yield(n,d):
        return n/d if n is not None and d is not None and d>0 else None
    @staticmethod
    def _r(v):
        return None if v is None else round(v,6)
