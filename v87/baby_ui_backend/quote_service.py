from __future__ import annotations
import os, time
from datetime import datetime, timezone
from typing import Callable
from .models import Quote

class QuoteService:
    """Quote boundary with conservative quality labels.

    Custom provider wins. Otherwise yfinance is an optional fallback and is ALWAYS labelled
    DELAYED because Baby cannot prove exchange-real-time entitlement from yfinance.
    """
    def __init__(self, provider:Callable[[str],dict]|None=None, ttl_seconds:float=8):
        self.provider=provider; self.ttl_seconds=ttl_seconds; self._cache={}

    def _yf(self,symbol):
        try:
            import yfinance as yf
            t=yf.Ticker(symbol)
            fi=getattr(t,'fast_info',None)
            price=getattr(fi,'last_price',None) if fi is not None else None
            prev=getattr(fi,'previous_close',None) if fi is not None else None
            high=getattr(fi,'day_high',None) if fi is not None else None
            low=getattr(fi,'day_low',None) if fi is not None else None
            vol=getattr(fi,'last_volume',None) if fi is not None else None
            if price is None: return None
            change=(price-prev) if prev not in (None,0) else None
            pct=(change/prev*100) if change is not None and prev else None
            return {'price':float(price),'change':change,'change_pct':pct,'volume':vol,'day_high':high,'day_low':low,'timestamp':datetime.now(timezone.utc).isoformat(),'quality':'DELAYED','provider':'YFINANCE_SECONDARY'}
        except Exception: return None

    def get(self,symbol:str)->Quote:
        symbol=symbol.upper(); now=time.monotonic(); cached=self._cache.get(symbol)
        if cached and now-cached[0] < self.ttl_seconds: return cached[1]
        try:
            d=(self.provider(symbol) if self.provider else None) or self._yf(symbol)
            if not d:
                q=Quote(symbol=symbol,price=None,quality='UNKNOWN',provider='UNCONFIGURED_OR_UNAVAILABLE')
            else:
                q=Quote(symbol=symbol,price=d.get('price'),change=d.get('change'),change_pct=d.get('change_pct'),bid=d.get('bid'),ask=d.get('ask'),volume=d.get('volume'),day_high=d.get('day_high'),day_low=d.get('day_low'),timestamp=d.get('timestamp') or datetime.now(timezone.utc).isoformat(),quality=d.get('quality','UNKNOWN'),provider=d.get('provider','UNKNOWN'))
        except Exception:
            q=Quote(symbol=symbol,price=None,quality='STALE',provider='ERROR')
        self._cache[symbol]=(now,q); return q
