import math
import pandas as pd
from .models import Fill

class RealisticExecutionEngine:
    """Daily-bar simulator.

    Signals formed after close on T execute at T+1 OPEN when available.
    Costs = fixed commission + slippage bps. Participation cap prevents a test
    from buying an unrealistic fraction of next-day volume.
    """
    def __init__(self,slippage_bps=5,commission=0.0,max_volume_participation=.02,
                 allow_fractional=False):
        self.slippage_bps=float(slippage_bps)
        self.commission=float(commission)
        self.max_volume_participation=float(max_volume_participation)
        self.allow_fractional=bool(allow_fractional)

    @staticmethod
    def _bar(frame,date):
        x=frame.loc[date]
        if hasattr(x,"iloc") and getattr(x,"ndim",1)>1:x=x.iloc[0]
        return x

    def execute_to_targets(self,signal_date,execution_date,target_weights,prices,
                           positions,cash,equity):
        fills=[]
        symbols=set(positions)|set(target_weights)
        # Sells first.
        for side_pass in ("SELL","BUY"):
            for sym in sorted(symbols):
                if sym not in prices or execution_date not in prices[sym].index:continue
                bar=self._bar(prices[sym],execution_date)
                open_px=float(bar["Open"])
                volume=float(bar.get("Volume",0) or 0)
                current=float(positions.get(sym,0))
                target_value=equity*float(target_weights.get(sym,0))
                target_shares=target_value/open_px if open_px>0 else 0
                delta=target_shares-current
                side="BUY" if delta>0 else "SELL"
                if side!=side_pass or abs(delta)<1e-12:continue
                qty=abs(delta)
                if not self.allow_fractional:qty=math.floor(qty)
                if qty<=0:continue
                if volume>0:qty=min(qty,volume*self.max_volume_participation)
                slip=open_px*self.slippage_bps/10000
                fill_px=open_px+slip if side=="BUY" else max(.0001,open_px-slip)
                notional=qty*fill_px;fee=self.commission
                if side=="BUY":
                    affordable=max(0,(cash-fee)/fill_px)
                    qty=min(qty,affordable)
                    if not self.allow_fractional:qty=math.floor(qty)
                    if qty<=0:continue
                    notional=qty*fill_px
                    cash-=notional+fee
                    positions[sym]=current+qty
                else:
                    qty=min(qty,current)
                    if qty<=0:continue
                    notional=qty*fill_px
                    cash+=notional-fee
                    positions[sym]=current-qty
                    if positions[sym]<=1e-12:positions.pop(sym,None)
                fills.append(Fill(str(signal_date.date()),str(execution_date.date()),sym,side,
                    float(qty),float(fill_px),float(notional),float(fee),
                    float(qty*slip),"rebalance"))
        return positions,cash,fills
