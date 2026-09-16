from __future__ import annotations
from dataclasses import dataclass, field, asdict, is_dataclass
from datetime import datetime, timezone
from typing import Any
import math
import pandas as pd

@dataclass
class ValidationCheck:
    name: str
    status: str
    observed: float | None = None
    reference: float | None = None
    difference_pct: float | None = None
    tolerance_pct: float | None = None
    source: str = ""
    authority: str = ""
    note: str = ""

@dataclass
class ValidationReport:
    status: str
    score: float
    checks_passed: int
    checks_review: int
    checks_failed: int
    checks_unknown: int
    checks: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    generated_at: str = ""
    schema_version: str = "4.7"

class ValidationEngine:
    """Audits Baby without converting absence into bearish evidence.

    Primary-source statuses are preserved: a REVIEW/PERIOD_MISMATCH metric cannot
    be promoted to PASS merely because a numeric value exists. Technical values
    are independently recalculated from raw OHLCV. External comparison packets
    are provider-agnostic and never replace SEC/FRED primary facts.
    """
    FIN_TOLERANCE_PCT = 2.0
    TECH_TOLERANCE_PCT = 0.35

    def validate(self, report:dict[str,Any], history:pd.DataFrame|None=None,
                 external_reference:dict[str,Any]|None=None)->ValidationReport:
        checks=[]; warnings=[]
        checks += self._primary_financial_checks(report)
        if history is not None and len(history)>=30:
            checks += self._technical_checks(report,history)
        else:
            checks.append(ValidationCheck("technical_recalculation","UNKNOWN",
                source="raw_ohlcv",authority="DERIVED",note="Insufficient/no price history supplied."))
        checks += self._external_checks(report,external_reference) if external_reference else [
            ValidationCheck("external_cross_source","UNKNOWN",source="external",authority="SECONDARY",
                            note="No genuinely independent external reference supplied.")]
        counts={s:sum(c.status==s for c in checks) for s in ("PASS","REVIEW","FAIL","UNKNOWN")}
        decided=counts["PASS"]+counts["REVIEW"]+counts["FAIL"]
        score=0.0 if not decided else 100*(counts["PASS"]+.5*counts["REVIEW"])/decided
        status="FAIL" if counts["FAIL"] else "REVIEW" if counts["REVIEW"] else "PASS" if decided else "UNKNOWN"
        if counts["UNKNOWN"]:
            warnings.append(f"{counts['UNKNOWN']} checks unresolved; UNKNOWN is excluded from validation score.")
        return ValidationReport(status,round(score,2),counts["PASS"],counts["REVIEW"],counts["FAIL"],
                                counts["UNKNOWN"],[asdict(c) for c in checks],warnings,
                                datetime.now(timezone.utc).isoformat())

    def _primary_financial_checks(self,r):
        pf=self._dict(r.get("primary_financial")); vf=self._dict(pf.get("verified_financials"))
        if not vf:
            return [ValidationCheck("primary_financial_presence","UNKNOWN",source="primary_financial",
                                    authority="PRIMARY",note="No verified primary financial packet.")]
        out=[]
        for name in ("revenue","net_income","free_cash_flow","operating_cash_flow","cash","debt"):
            m=self._dict(vf.get(name)); val=m.get("value"); raw=str(m.get("status") or "").upper(); conf=m.get("confidence")
            if val is None:
                out.append(ValidationCheck(f"primary.{name}","UNKNOWN",source="primary_financial",
                                           authority="PRIMARY",note="Metric unresolved/missing.")); continue
            # Preserve the upstream evidence state. REVIEW is never upgraded.
            if raw in {"MATERIAL_DISAGREEMENT","QUARANTINED","QUARANTINED_SERIES_DISCONTINUITY"}:
                status="FAIL" if raw=="QUARANTINED" else "REVIEW"
            elif raw in {"REVIEW","PERIOD_MISMATCH","LOW_CONFIDENCE","UNRESOLVED"}:
                status="REVIEW"
            else:
                status="PASS"
            out.append(ValidationCheck(f"primary.{name}",status,float(val),source="primary_financial",
                                       authority="PRIMARY",note=f"upstream_status={raw or 'AVAILABLE'} confidence={conf}"))
        return out

    def _technical_checks(self,r,h):
        t=self._dict(r.get("technical")); close=self._close(h)
        if len(close)<30:return [ValidationCheck("technical_recalculation","UNKNOWN",source="raw_ohlcv",authority="DERIVED")]
        refs={"sma_20":float(close.tail(20).mean())}
        if len(close)>=50: refs["sma_50"]=float(close.tail(50).mean())
        refs["ema_20"]=float(close.ewm(span=20,adjust=False).mean().iloc[-1])
        d=close.diff(); g=d.clip(lower=0); l=-d.clip(upper=0)
        ag=g.ewm(alpha=1/14,adjust=False,min_periods=14).mean(); al=l.ewm(alpha=1/14,adjust=False,min_periods=14).mean()
        if pd.notna(ag.iloc[-1]) and pd.notna(al.iloc[-1]):
            refs["rsi_14"]=100.0 if al.iloc[-1]==0 and ag.iloc[-1]>0 else 50.0 if al.iloc[-1]==0 else 100-(100/(1+ag.iloc[-1]/al.iloc[-1]))
        out=[]
        aliases={"sma_20":("sma_20","sma20"),"sma_50":("sma_50","sma50"),
                 "ema_20":("ema_20","ema20"),"rsi_14":("rsi_14","rsi14")}
        for k,ref in refs.items():
            obs=self._first_num(t,*aliases[k])
            if obs is None:
                out.append(ValidationCheck(f"technical.{k}","UNKNOWN",reference=ref,source="raw_ohlcv_recalculation",
                                           authority="DERIVED",note="Analyzer did not expose comparable metric.")); continue
            diff=self._diff(obs,ref); tol=1.0 if k=="rsi_14" else self.TECH_TOLERANCE_PCT
            out.append(ValidationCheck(f"technical.{k}","PASS" if diff<=tol else "REVIEW",
                                       obs,ref,round(diff,4),tol,"raw_ohlcv_recalculation","DERIVED"))
        return out

    def _external_checks(self,r,ext):
        mapping={"revenue":"primary_financial.verified_financials.revenue.value",
                 "net_income":"primary_financial.verified_financials.net_income.value",
                 "free_cash_flow":"primary_financial.verified_financials.free_cash_flow.value",
                 "cash":"primary_financial.verified_financials.cash.value",
                 "debt":"primary_financial.verified_financials.debt.value",
                 "current_price":"market.current_price"}
        out=[]; source=str(ext.get("source") or "external"); asof=ext.get("as_of")
        for k,path in mapping.items():
            ref=ext.get(k)
            if not self._isnum(ref): continue
            obs=self._path(r,path)
            if not self._isnum(obs):
                out.append(ValidationCheck(f"external.{k}","UNKNOWN",reference=float(ref),source=source,
                                           authority="SECONDARY",note=f"as_of={asof}")); continue
            diff=self._diff(float(obs),float(ref)); tol=.5 if k=="current_price" else self.FIN_TOLERANCE_PCT
            st="PASS" if diff<=tol else "REVIEW" if diff<=tol*5 else "FAIL"
            out.append(ValidationCheck(f"external.{k}",st,float(obs),float(ref),round(diff,4),tol,
                                       source,"SECONDARY",f"as_of={asof}"))
        return out or [ValidationCheck("external_cross_source","UNKNOWN",source=source,authority="SECONDARY",
                                      note="Reference packet contained no comparable canonical metrics.")]

    @staticmethod
    def _close(h):
        x=h.copy()
        if isinstance(x.columns,pd.MultiIndex): x.columns=[str(c[0]) for c in x.columns]
        cmap={str(c).strip().lower():c for c in x.columns}; c=cmap.get("close")
        return pd.Series(dtype=float) if c is None else pd.to_numeric(x[c],errors="coerce").dropna()
    @staticmethod
    def _dict(x):
        if x is None:return {}
        if isinstance(x,dict):return x
        if is_dataclass(x):return asdict(x)
        return vars(x) if hasattr(x,"__dict__") else {}
    @staticmethod
    def _first_num(d,*keys):
        for k in keys:
            v=d.get(k)
            if ValidationEngine._isnum(v):return float(v)
        return None
    @staticmethod
    def _isnum(v): return isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(float(v))
    @staticmethod
    def _path(d,path):
        cur=d
        for p in path.split("."):
            cur=ValidationEngine._dict(cur).get(p)
            if cur is None:return None
        return cur
    @staticmethod
    def _diff(a,b): return abs(a-b)/max(abs(b),1e-12)*100
