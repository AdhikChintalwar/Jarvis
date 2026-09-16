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
    coverage: float
    checks_passed: int
    checks_review: int
    checks_failed: int
    checks_unknown: int
    checks: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    generated_at: str = ""
    schema_version: str = "4.8.4"

class ValidationEngine:
    """Evidence-authority preserving validation.

    PRIMARY facts remain authoritative. Independent secondary evidence can
    corroborate or challenge them, but can never overwrite them. UNKNOWN is
    excluded from score and separately reduces validation coverage.
    """
    FIN_TOLERANCE_PCT = 2.0
    BALANCE_SHEET_REVIEW_TOLERANCE_PCT = 2.0
    BALANCE_SHEET_MATERIAL_TOLERANCE_PCT = 10.0
    PRICE_TOLERANCE_PCT = 0.75
    TECH_TOLERANCE_PCT = 0.75
    RSI_TOLERANCE_ABS = 1.5

    def validate(self, report:dict[str,Any], history:pd.DataFrame|None=None,
                 external_reference:dict[str,Any]|None=None)->ValidationReport:
        checks=[]; warnings=[]
        checks += self._primary_financial_checks(report)
        if history is not None and len(history)>=30:
            checks += self._technical_checks(report,history)
        else:
            checks.append(ValidationCheck("technical_recalculation","UNKNOWN",
                source="raw_ohlcv",authority="DERIVED",note="Insufficient/no price history supplied."))

        if external_reference:
            checks += self._external_checks(report,external_reference)
        else:
            checks.append(ValidationCheck("external_cross_source","UNKNOWN",source="external",
                authority="INDEPENDENT_SECONDARY",note="No genuinely independent external reference supplied."))

        counts={s:sum(c.status==s for c in checks) for s in ("PASS","REVIEW","FAIL","UNKNOWN")}
        total=len(checks); decided=total-counts["UNKNOWN"]
        coverage=0.0 if not total else 100.0*decided/total
        score=0.0 if not decided else 100*(counts["PASS"]+.5*counts["REVIEW"])/decided
        status="FAIL" if counts["FAIL"] else "REVIEW" if counts["REVIEW"] else "PASS" if decided else "UNKNOWN"
        if counts["UNKNOWN"]:
            warnings.append(f"{counts['UNKNOWN']} checks unresolved; UNKNOWN is excluded from validation score.")
        return ValidationReport(status,round(score,2),round(coverage,2),
            counts["PASS"],counts["REVIEW"],counts["FAIL"],counts["UNKNOWN"],
            [asdict(c) for c in checks],warnings,datetime.now(timezone.utc).isoformat())

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
        rsi=self._rsi(close)
        if rsi is not None: refs["rsi_14"]=rsi
        out=[]
        aliases={"sma_20":("sma_20","sma20"),"sma_50":("sma_50","sma50"),
                 "ema_20":("ema_20","ema20"),"rsi_14":("rsi_14","rsi14")}
        for k,ref in refs.items():
            obs=self._first_num(t,*aliases[k])
            if obs is None:
                out.append(ValidationCheck(f"technical.{k}","UNKNOWN",reference=ref,source="raw_ohlcv_recalculation",
                    authority="DERIVED",note="Analyzer did not expose comparable metric.")); continue
            diff=self._diff(obs,ref); tol=1.0 if k=="rsi_14" else .35
            out.append(ValidationCheck(f"technical.{k}","PASS" if diff<=tol else "REVIEW",
                obs,ref,round(diff,4),tol,"raw_ohlcv_recalculation","DERIVED"))
        return out

    def _external_checks(self,r,ext):
        source=str(ext.get("source") or ext.get("provider") or "external")
        if ext.get("independent") is not True:
            return [ValidationCheck("external_cross_source","UNKNOWN",source=source,
                authority="INDEPENDENT_SECONDARY",note="External packet rejected: independent=True was not explicitly supplied.")]
        if str(ext.get("status") or "ACTIVE").upper() not in {"ACTIVE","PARTIAL"}:
            return [ValidationCheck("external_cross_source","UNKNOWN",source=source,
                authority="INDEPENDENT_SECONDARY",note=f"Independent provider status={ext.get('status')}; warnings={ext.get('warnings') or []}")]
        mappings={
            "revenue":("primary_financial.verified_financials.revenue.value","FIN"),
            "net_income":("primary_financial.verified_financials.net_income.value","FIN"),
            "operating_cash_flow":("primary_financial.verified_financials.operating_cash_flow.value","FIN"),
            "free_cash_flow":("primary_financial.verified_financials.free_cash_flow.value","FIN"),
            "cash":("primary_financial.verified_financials.cash.value","BALANCE_CONCEPT"),
            "debt":("primary_financial.verified_financials.debt.value","BALANCE_CONCEPT"),
            "current_price":("market.current_price","PRICE"), "sma_20":("technical.sma_20","TECH"),
            "sma_50":("technical.sma_50","TECH"), "ema_20":("technical.ema_20","TECH"),
            "rsi_14":("technical.rsi_14","RSI")}
        out=[]
        for k,(path,kind) in mappings.items():
            ref=ext.get(k)
            note=f"provider={ext.get('provider') or source}; market_as_of={ext.get('market_as_of')}; financial_as_of={ext.get('financial_as_of')}"
            if not self._isnum(ref):
                out.append(ValidationCheck(f"external.{k}","UNKNOWN",source=source,authority="INDEPENDENT_SECONDARY",
                    note=note+"; provider did not supply a comparable value.")); continue
            obs=self._path(r,path)
            if not self._isnum(obs):
                out.append(ValidationCheck(f"external.{k}","UNKNOWN",reference=float(ref),source=source,authority="INDEPENDENT_SECONDARY",
                    note=note+"; Baby did not expose a comparable value.")); continue
            if kind=="RSI":
                delta=abs(float(obs)-float(ref))
                st="PASS" if delta<=self.RSI_TOLERANCE_ABS else "REVIEW" if delta<=5 else "FAIL"
                out.append(ValidationCheck(f"external.{k}",st,float(obs),float(ref),round(delta,4),
                    self.RSI_TOLERANCE_ABS,source,"INDEPENDENT_SECONDARY",note+"; difference is RSI points; disagreement preserved.")); continue
            diff=self._diff(float(obs),float(ref))
            if kind=="BALANCE_CONCEPT":
                # Cash and debt are stock concepts whose vendor definitions can
                # legitimately differ (restricted cash, ST investments, lease
                # liabilities, current debt, total debt aggregation, etc.).
                # Preserve disagreement but do not declare the PRIMARY SEC value
                # wrong solely from percentage distance.
                if diff <= self.BALANCE_SHEET_REVIEW_TOLERANCE_PCT:
                    st="PASS"
                    concept_note="STRONG_AGREEMENT"
                elif diff <= self.BALANCE_SHEET_MATERIAL_TOLERANCE_PCT:
                    st="REVIEW"
                    concept_note="CONCEPT_OR_PERIOD_RECONCILIATION"
                else:
                    st="REVIEW"
                    concept_note="CONCEPT_MISMATCH_MATERIAL"
                out.append(ValidationCheck(
                    f"external.{k}",st,float(obs),float(ref),round(diff,4),
                    self.BALANCE_SHEET_REVIEW_TOLERANCE_PCT,source,
                    "INDEPENDENT_SECONDARY",
                    note+f"; {concept_note}; primary SEC authority preserved."
                ))
                continue

            tol=self.PRICE_TOLERANCE_PCT if kind=="PRICE" else self.TECH_TOLERANCE_PCT if kind=="TECH" else self.FIN_TOLERANCE_PCT
            st="PASS" if diff<=tol else "REVIEW" if diff<=tol*5 else "FAIL"
            out.append(ValidationCheck(f"external.{k}",st,float(obs),float(ref),round(diff,4),tol,source,"INDEPENDENT_SECONDARY",note))
        return out

    @staticmethod
    def _rsi(close):
        d=close.diff();g=d.clip(lower=0);l=-d.clip(upper=0)
        ag=g.ewm(alpha=1/14,adjust=False,min_periods=14).mean();al=l.ewm(alpha=1/14,adjust=False,min_periods=14).mean()
        if len(ag)==0 or pd.isna(ag.iloc[-1]) or pd.isna(al.iloc[-1]):return None
        return 100.0 if al.iloc[-1]==0 and ag.iloc[-1]>0 else 50.0 if al.iloc[-1]==0 else float(100-(100/(1+ag.iloc[-1]/al.iloc[-1])))
    @staticmethod
    def _close(h):
        x=h.copy()
        if isinstance(x.columns,pd.MultiIndex): x.columns=[str(c[0]) for c in x.columns]
        cmap={str(c).strip().lower():c for c in x.columns};c=cmap.get("close")
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
    def _isnum(v):return isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(float(v))
    @staticmethod
    def _path(d,path):
        cur=d
        for p in path.split("."):
            cur=ValidationEngine._dict(cur).get(p)
            if cur is None:return None
        return cur
    @staticmethod
    def _diff(a,b):return abs(a-b)/max(abs(b),1e-12)*100
