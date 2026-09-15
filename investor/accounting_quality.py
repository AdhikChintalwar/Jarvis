from __future__ import annotations
from dataclasses import dataclass,field
from typing import Optional
from investor.financial_evidence import FinancialEvidenceContext

@dataclass
class AccountingQualityReport:
    score:float=50.;confidence:float=0.;coverage:float=0.
    history_periods:int=0;history_confidence:float=0.
    cash_conversion:Optional[float]=None;fcf_margin:Optional[float]=None
    cash_earnings_gap_ratio:Optional[float]=None;net_cash:Optional[float]=None
    cash_to_debt:Optional[float]=None;shares_change_yoy:Optional[float]=None
    operating_margin_change_pp:Optional[float]=None;net_margin_change_pp:Optional[float]=None
    fcf_margin_change_pp:Optional[float]=None;diluted_shares_change_yoy:Optional[float]=None
    positive_signals:list[str]=field(default_factory=list);red_flags:list[str]=field(default_factory=list)
    unknowns:list[str]=field(default_factory=list);evidence:dict=field(default_factory=dict)

class AccountingQualityEngine:
    SIGNALS=("cash_conversion","fcf_margin","cash_earnings_gap","net_cash_position","share_change",
             "operating_margin_trend","net_margin_trend","fcf_margin_trend")

    def analyze(self, primary_financial):
        if not primary_financial:return AccountingQualityReport(unknowns=list(self.SIGNALS))
        ev=FinancialEvidenceContext(primary_financial);hist=(primary_financial.get("annual_history",{}).get("periods",[]) or [])
        evidence={};con=[];pos=[];red=[];unk=[]
        def d(name,names,value):
            aa=[]
            for n in names:
                m=ev.metric(n)
                if not m.available:
                    evidence[name]={"available":False,"authority":0.,"inputs":names};return 0.
                aa.append(m.authority)
            a=min(aa) if aa else 0.; evidence[name]={"available":value is not None,"authority":a if value is not None else 0.,"inputs":names}
            return a if value is not None else 0.
        rev,ni,ocf,fcf,cash,debt,shares=[ev.metric(x) for x in ("revenue","net_income","operating_cash_flow","free_cash_flow","cash","debt","shares_change_yoy")]
        cc=self._ratio(ocf.value,ni.value) if ni.available and ni.value is not None and ni.value>0 else None
        a=d("cash_conversion",["operating_cash_flow","net_income"],cc)
        if a:
            if cc>=1:con.append((15,a));pos.append("Operating cash flow covers reported net income.")
            elif cc<.6:con.append((-15,a));red.append("Weak cash conversion versus reported net income.")
            elif cc<.8:con.append((-7,a));red.append("Cash conversion trails reported earnings.")
            else:con.append((5,a))
        elif ni.available and ni.value is not None and ni.value<=0 and ocf.available and ocf.value is not None and ocf.value>0:
            # OCF/net-income is not meaningful when earnings are zero/negative.
            evidence["cash_generation_despite_losses"]={"available":True,"authority":min(ni.authority,ocf.authority),"inputs":["net_income","operating_cash_flow"]}
            con.append((8,min(ni.authority,ocf.authority)));pos.append("Operating cash flow is positive despite reported losses.")
            unk.append("cash_conversion_not_meaningful")
        else:unk.append("cash_conversion")
        fm=self._ratio(fcf.value,rev.value);a=d("fcf_margin",["free_cash_flow","revenue"],fm)
        if a:
            if fm>=.2:con.append((12,a));pos.append("Free-cash-flow margin is strong.")
            elif fm>=.1:con.append((7,a))
            elif fm<0:con.append((-14,a));red.append("Free cash flow is negative relative to revenue.")
            elif fm<.03:con.append((-5,a))
        else:unk.append("fcf_margin")
        gap=(ni.value-ocf.value)/abs(rev.value) if rev.available and ni.available and ocf.available and rev.value else None
        a=d("cash_earnings_gap",["net_income","operating_cash_flow","revenue"],gap)
        if a:
            if gap>.1:con.append((-12,a));red.append("Reported earnings materially exceed operating cash flow.")
            elif gap<-.05:con.append((7,a));pos.append("Operating cash flow materially exceeds reported earnings.")
            else:con.append((3,a))
        else:unk.append("cash_earnings_gap")
        net=None;ratio=None
        if cash.available and debt.available:
            net=cash.value-debt.value;ratio=cash.value/debt.value if debt.value and debt.value>0 else (float("inf") if cash.value>0 else None)
        a=d("net_cash_position",["cash","debt"],net)
        if a:
            if net>0:con.append((10,a));pos.append("Cash exceeds debt.")
            elif ratio is not None and ratio<.25:con.append((-12,a));red.append("Cash is low relative to debt.")
            elif ratio is not None and ratio<.5:con.append((-6,a))
        else:unk.append("net_cash_position")
        sc=shares.value if shares.available else None;a=shares.authority if shares.available else 0.
        evidence["share_change"]={"available":bool(a),"authority":a,"inputs":["shares_change_yoy"]}
        if a:
            if sc>=.1:con.append((-16,a));red.append("Comparable shares outstanding increased at least 10% year over year.")
            elif sc>=.03:con.append((-8,a));red.append("Comparable shares outstanding increased year over year.")
            elif sc<=-.03:con.append((8,a));pos.append("Comparable shares outstanding declined year over year.")
        else:unk.append("share_change")
        history_periods=len(hist)
        history_confidence=.90 if history_periods>=5 else .80 if history_periods>=4 else .70 if history_periods>=3 else .55 if history_periods>=2 else 0.
        evidence["_history_periods"]=history_periods
        op=self._change(hist,"operating_margin");nm=self._change(hist,"net_margin");fc=self._change(hist,"free_cash_flow_margin")
        ds=self._yoy(hist,"weighted_average_diluted_shares")
        self._trend("operating_margin_trend",op,evidence,con,pos,red,unk,8,-10,"Operating margin improved year over year.","Operating margin deteriorated materially year over year.")
        self._trend("net_margin_trend",nm,evidence,con,pos,red,unk,7,-9,"Net margin improved year over year.","Net margin deteriorated materially year over year.")
        self._trend("fcf_margin_trend",fc,evidence,con,pos,red,unk,7,-9,"Free-cash-flow margin improved year over year.","Free-cash-flow margin deteriorated materially year over year.")
        avail=sum(bool(evidence.get(n,{}).get("available")) for n in self.SIGNALS)
        auth=[evidence.get(n,{}).get("authority",0.) for n in self.SIGNALS]
        raw=sum(delta*a for delta,a in con)
        # Positive evidence has diminishing returns so several correlated strengths
        # cannot casually saturate the score. Negative evidence remains fully active.
        calibrated = raw if raw<=0 else 50.0*(1.0-(2.718281828459045**(-raw/50.0)))
        score=max(0.,min(100.,50+calibrated))
        # Evidence-depth ceiling affects only extreme positive scores. It does not
        # make missing data bearish; it prevents "perfect" scores on shallow history.
        depth_ceiling=99.0 if history_periods>=5 else 96.0 if history_periods>=4 else 93.0 if history_periods>=3 else 90.0 if history_periods>=2 else 85.0
        if score>50: score=min(score,depth_ceiling)
        return AccountingQualityReport(
            score=round(score,2),
            confidence=round(sum(auth)/len(self.SIGNALS)*100,2),
            coverage=round(avail/len(self.SIGNALS)*100,2),
            history_periods=history_periods,
            history_confidence=round(history_confidence*100,2),
            cash_conversion=self._r(cc),fcf_margin=self._r(fm),
            cash_earnings_gap_ratio=self._r(gap),net_cash=self._r(net),
            cash_to_debt=self._r(ratio),shares_change_yoy=self._r(sc),
            operating_margin_change_pp=self._pp(op),net_margin_change_pp=self._pp(nm),
            fcf_margin_change_pp=self._pp(fc),diluted_shares_change_yoy=self._r(ds),
            positive_signals=pos,red_flags=red,unknowns=unk,evidence=evidence
        )
    @staticmethod
    def _ratio(a,b):return None if a is None or b in (None,0) else a/b
    @staticmethod
    def _change(h,k):
        r=[x for x in h if x.get(k) is not None];return None if len(r)<2 else r[-1][k]-r[-2][k]
    @staticmethod
    def _yoy(h,k):
        r=[x for x in h if x.get(k) not in (None,0)];return None if len(r)<2 else r[-1][k]/r[-2][k]-1
    @staticmethod
    def _trend(name,ch,e,c,p,r,u,up,down,pt,rt):
        periods=e.get("_history_periods",0)
        hist_auth=.85 if periods>=5 else .75 if periods>=3 else .60 if periods>=2 else 0.
        a=hist_auth if ch is not None else 0.;e[name]={"available":ch is not None,"authority":a,"inputs":["annual_history"],"history_periods":periods}
        if ch is None:u.append(name)
        elif ch>=.03:c.append((up,a));p.append(pt)
        elif ch<=-.03:c.append((down,a));r.append(rt)
    @staticmethod
    def _r(v):
        if v is None or v==float("inf"):return v
        return round(v,6)
    @staticmethod
    def _pp(v):return None if v is None else round(v*100,2)
