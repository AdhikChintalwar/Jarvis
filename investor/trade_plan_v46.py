from __future__ import annotations
from dataclasses import dataclass, field, asdict, is_dataclass
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any
import math
import pandas as pd
from investor.trade_plan import TradePlanEngine
from investor.position_sizing import PositionSizingEngine

@dataclass
class Scenario:
    status: str
    entry_low: float|None=None
    entry_high: float|None=None
    planned_entry: float|None=None
    trigger: float|None=None
    invalidation: float|None=None
    target_1: float|None=None
    target_2: float|None=None
    risk_reward_1: float|None=None
    risk_reward_2: float|None=None
    note: str=""

@dataclass
class TradePlanV47:
    status: str
    current_price: float|None
    pullback: dict
    breakout: dict
    current_setup: dict
    support_1: float|None
    support_2: float|None
    resistance_1: float|None
    resistance_2: float|None
    atr_14: float|None
    valuation_context: str
    decision_score: float
    research_state: str
    risk_level: str
    hard_risk_override: bool
    market_data_source: str
    market_data_as_of: str|None
    history_observations: int
    position: dict|None=None
    notes:list[str]=field(default_factory=list)
    generated_at:str=""
    schema_version:str="4.7"

# Backward-compatible public name for V4.6 callers/tests.
TradePlanV46 = TradePlanV47

class TradePlanAgent:
    """Deterministic research scenarios. It never submits an order."""
    def __init__(self):
        self.structure=TradePlanEngine(); self.sizer=PositionSizingEngine()

    @staticmethod
    def _legacy_technical_adapter(technical, history, atr):
        """Complete compatibility packet for the legacy TradePlanBuilder.

        Every technical attribute consumed by the legacy builder is populated.
        Deterministically derivable values come from the supplied OHLC history.
        Non-derivable optional values receive conservative neutral defaults so a
        synthetic/incomplete packet cannot crash trade-plan research.

        This adapter is compatibility-only: it does not alter DecisionEngine,
        ValidationEngine, scoring authority, or the analyzer's source object.
        """
        if isinstance(technical, dict):
            td = dict(technical)
        elif hasattr(technical, "__dict__"):
            td = dict(vars(technical))
        else:
            td = {}

        h = history.copy()
        if isinstance(h.columns, pd.MultiIndex):
            h.columns = [str(c[0]) for c in h.columns]
        cmap = {str(c).strip().lower(): c for c in h.columns}
        close_col = cmap.get("close")
        close = (
            pd.to_numeric(h[close_col], errors="coerce").dropna()
            if close_col is not None else pd.Series(dtype=float)
        )

        def sma(n):
            return float(close.tail(n).mean()) if len(close) >= n else None

        def ema(n):
            return (
                float(close.ewm(span=n, adjust=False).mean().iloc[-1])
                if len(close) >= n else None
            )

        def rsi14():
            if len(close) < 15:
                return None
            d = close.diff()
            gain = d.clip(lower=0)
            loss = -d.clip(upper=0)
            ag = gain.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
            al = loss.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
            if pd.isna(ag.iloc[-1]) or pd.isna(al.iloc[-1]):
                return None
            if al.iloc[-1] == 0:
                return 100.0 if ag.iloc[-1] > 0 else 50.0
            return float(100 - 100 / (1 + ag.iloc[-1] / al.iloc[-1]))

        # Normalize aliases first.
        aliases = {
            "sma20": "sma_20", "sma50": "sma_50", "sma200": "sma_200",
            "ema20": "ema_20", "ema50": "ema_50", "ema200": "ema_200",
            "rsi14": "rsi_14", "atr14": "atr_14",
        }
        for old, canonical in aliases.items():
            if td.get(canonical) is None and td.get(old) is not None:
                td[canonical] = td[old]

        derived = {
            "atr_14": atr,
            "sma_20": sma(20),
            "sma_50": sma(50),
            "sma_200": sma(200),
            "ema_20": ema(20),
            "ema_50": ema(50),
            "ema_200": ema(200),
            "rsi_14": rsi14(),
        }
        for key, value in derived.items():
            if td.get(key) is None:
                td[key] = value

        current = float(close.iloc[-1]) if len(close) else None
        ema20 = td.get("ema_20")
        if td.get("distance_from_ema20_pct") is None:
            if current is not None and ema20 not in (None, 0):
                td["distance_from_ema20_pct"] = (current / float(ema20) - 1.0) * 100.0
            else:
                td["distance_from_ema20_pct"] = 0.0

        # Complete all attributes read by the legacy builder. These are neutral
        # compatibility defaults only when a value cannot be derived or supplied.
        neutral_defaults = {
            "atr_14": 0.0,
            "ema_20": current,
            "ema_50": current,
            "rsi_14": 50.0,
            "sma_20": current,
            "sma_50": current,
            "distance_from_ema20_pct": 0.0,
        }
        for key, value in neutral_defaults.items():
            if td.get(key) is None:
                td[key] = value

        return SimpleNamespace(**td)

    @staticmethod
    def _legacy_risk_adapter(risk):
        """Complete compatibility packet for the legacy TradePlanBuilder.

        This is an interface adapter only. It never changes UnifiedRiskEngine
        authority or DecisionEngine constraints. Missing legacy analytics are
        neutralized solely to prevent incomplete/synthetic packets from crashing.
        """
        if isinstance(risk, dict):
            rd = dict(risk)
        elif hasattr(risk, "__dict__"):
            rd = dict(vars(risk))
        else:
            rd = {}

        aliases = {
            "volatility": "annualized_volatility",
            "annual_volatility": "annualized_volatility",
            "max_drawdown_pct": "max_drawdown",
            "average_volume": "avg_volume",
            "average_dollar_volume": "avg_dollar_volume",
        }
        for old, canonical in aliases.items():
            if rd.get(canonical) is None and rd.get(old) is not None:
                rd[canonical] = rd[old]

        # Neutral compatibility defaults. These are NOT evidence and are not
        # permitted to override the sovereign unified-risk/hard-risk gate.
        neutral_defaults = {
            "annualized_volatility": 0.0,
            "max_drawdown": 0.0,
            "avg_volume": 0.0,
            "avg_dollar_volume": 0.0,
            "beta": 1.0,
        }
        for key, value in neutral_defaults.items():
            if rd.get(key) is None:
                rd[key] = value

        return SimpleNamespace(**rd)

    def build(self, report:dict[str,Any], history:pd.DataFrame, decision,
              account_size:float|None=None, base_risk_percent:float=.5,
              max_position_percent:float=10.0)->TradePlanV47:
        h=self._history(history)
        if len(h)<50: raise ValueError("TradePlanAgent requires at least 50 valid OHLC rows")
        current=float(h["Close"].iloc[-1]); technical=report.get("technical"); legacy=report.get("risk")
        if technical is None or legacy is None: raise ValueError("technical and risk reports required")
        d=self._dict(decision); state=str(d.get("research_state") or "WATCH").upper(); score=float(d.get("score") or 50)
        thesis="AVOID" if state=="AVOID" else "WAIT" if state=="WAIT" else "WATCH"
        atr=self._atr(h)
        technical_for_structure=self._legacy_technical_adapter(technical,h,atr)
        risk_for_structure=self._legacy_risk_adapter(legacy)
        base=self.structure.build(h,technical_for_structure,risk_for_structure,SimpleNamespace(decision=thesis))
        unified=self._dict(report.get("unified_risk")); level=str(unified.get("risk_level") or "UNKNOWN").upper()
        hard=bool(unified.get("hard_overrides"))
        val=self._dict(report.get("valuation")); vs=self._num(val.get("score"))
        vctx="UNKNOWN" if vs is None else "ATTRACTIVE" if vs>=65 else "NEUTRAL" if vs>=40 else "DEMANDING"

        # Pullback scenario is judged from its own planned entry. Resistances that
        # price has already cleared are labeled pullback targets, never current upside.
        lo,hi=base.preferred_entry_low,base.preferred_entry_high
        planned=(lo+hi)/2 if lo is not None and hi is not None else None
        stop=base.stop_loss
        pt=[x for x in (base.resistance_1,base.resistance_2) if x is not None and planned is not None and x>planned]
        if planned is not None and atr:
            while len(pt)<2: pt.append(planned+atr*(2+len(pt)))
        t1=pt[0] if pt else None; t2=pt[1] if len(pt)>1 else None
        rr1=self._rr(planned,stop,t1); rr2=self._rr(planned,stop,t2)
        pull_status="UNAVAILABLE" if planned is None or stop is None else "PULLBACK_RESEARCH_ONLY" if hi is not None and hi<current else "AT_PULLBACK_ZONE"
        pull=Scenario(pull_status,self._r(lo),self._r(hi),self._r(planned),None,self._r(stop),
                      self._r(t1),self._r(t2),self._r(rr1),self._r(rr2),
                      "Targets belong to the pullback-entry scenario and may be below today's market price.")

        # Current/breakout scenario only uses future resistance above current.
        future=[x for x in (base.resistance_1,base.resistance_2) if x is not None and x>current]
        resistance=future[0] if future else None
        trigger=(resistance+max(current*.002,(atr or 0)*.10)) if resistance else None
        bstop=(resistance-(atr or current*.03)) if resistance else None
        bt1=(trigger+2*(trigger-bstop)) if trigger and bstop and trigger>bstop else None
        bt2=(trigger+3*(trigger-bstop)) if trigger and bstop and trigger>bstop else None
        breakout=Scenario("BREAKOUT_RESEARCH" if trigger else "NO_CONFIRMED_FUTURE_RESISTANCE",
                          trigger=self._r(trigger),invalidation=self._r(bstop),
                          target_1=self._r(bt1),target_2=self._r(bt2),
                          risk_reward_1=2.0 if bt1 else None,risk_reward_2=3.0 if bt2 else None,
                          note="Breakout targets are deterministic risk-multiple scenarios, not intrinsic fair values.")

        constrained=hard or level in {"VERY_HIGH","EXTREME"} or state in {"WAIT","AVOID"}
        if constrained:
            current_status="WAIT_RISK_CONSTRAINED"
            reason="Hard/unified risk or deterministic decision state constrains a new-long setup."
        elif hi is not None and lo is not None and lo<=current<=hi:
            current_status="AT_PULLBACK_ZONE"; reason="Current price is inside the deterministic pullback zone."
        elif trigger is not None and current>=trigger:
            current_status="BREAKOUT_TRIGGERED"; reason="Current price is above the calculated breakout trigger."
        elif hi is not None and current>hi:
            current_status="WAIT_FOR_PULLBACK_OR_BREAKOUT"; reason="Price is above pullback zone and breakout is not confirmed."
        else:
            current_status="NO_VALID_CURRENT_STRUCTURE"; reason="No valid current-price long structure is confirmed."

        notes=[]
        if vctx=="DEMANDING":notes.append("Valuation is demanding; technical structure does not override valuation.")
        if constrained:notes.append("Risk/decision constraints remain sovereign over technical attractiveness.")
        if t1 is not None and t1<=current:notes.append("Pullback target 1 is below current price and is not a current upside target.")
        if t2 is not None and t2<=current:notes.append("Pullback target 2 is below current price and is not a current upside target.")

        pos=None
        mult=float(unified.get("position_risk_multiplier") or 1)
        if account_size and not constrained and planned and stop and planned>stop:
            x=self.sizer.calculate(account_size,planned,stop,max(.05,base_risk_percent*mult),max_position_percent*mult)
            pos=asdict(x);pos["unified_risk_multiplier"]=mult

        return TradePlanV47(current_status,self._r(current),asdict(pull),asdict(breakout),
                            {"status":current_status,"reason":reason},
                            self._r(base.support_1),self._r(base.support_2),self._r(base.resistance_1),self._r(base.resistance_2),
                            self._r(atr),vctx,round(score,2),state,level,hard,
                            "Yahoo Finance via yfinance (secondary/prototype)",self._asof(h),len(h),pos,notes,
                            datetime.now(timezone.utc).isoformat())

    @staticmethod
    def _history(h):
        x=h.copy()
        if isinstance(x.columns,pd.MultiIndex):x.columns=[str(c[0]) for c in x.columns]
        cmap={str(c).strip().lower():c for c in x.columns}
        ren={cmap[k]:k.title() for k in ("open","high","low","close","volume") if k in cmap}
        x=x.rename(columns=ren)
        if any(c not in x.columns for c in ("High","Low","Close")):return pd.DataFrame()
        for c in ("High","Low","Close"):x[c]=pd.to_numeric(x[c],errors="coerce")
        return x.dropna(subset=["High","Low","Close"]).sort_index()
    @staticmethod
    def _atr(h):
        prev=h["Close"].shift();tr=pd.concat([(h["High"]-h["Low"]).abs(),(h["High"]-prev).abs(),(h["Low"]-prev).abs()],axis=1).max(axis=1)
        v=tr.ewm(alpha=1/14,adjust=False,min_periods=14).mean().iloc[-1];return None if pd.isna(v) else float(v)
    @staticmethod
    def _rr(e,s,t):
        if None in (e,s,t) or e<=s or t<=e:return None
        return (t-e)/(e-s)
    @staticmethod
    def _dict(x):
        if x is None:return {}
        if isinstance(x,dict):return x
        if is_dataclass(x):return asdict(x)
        return vars(x) if hasattr(x,"__dict__") else {}
    @staticmethod
    def _num(v):return float(v) if isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(float(v)) else None
    @staticmethod
    def _r(v):return None if v is None or not math.isfinite(float(v)) else round(float(v),2)
    @staticmethod
    def _asof(h):
        try:return pd.Timestamp(h.index[-1]).isoformat()
        except:return str(h.index[-1])
