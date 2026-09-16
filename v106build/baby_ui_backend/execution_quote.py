from __future__ import annotations

import math
import os
from datetime import datetime, timezone
from typing import Any

from .alpaca_market import AlpacaMarketScreener
from .quote_service import QuoteService


def _num(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def _parse_ts(value):
    if not value:
        return None
    try:
        s = str(value).strip().replace('Z', '+00:00')
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


class ExecutionQuoteService:
    """Current-state quote boundary for trade/paper eligibility.

    Alpaca market data is preferred because it is independent of the yfinance research
    history path. A secondary quote may still be returned for display, but it is never
    silently upgraded to execution-grade evidence.
    """

    def __init__(self, fallback: QuoteService | None = None, alpaca: AlpacaMarketScreener | None = None):
        self.fallback = fallback or QuoteService()
        self.alpaca = alpaca or AlpacaMarketScreener()
        self.max_age_seconds = float(os.getenv('BABY_EXECUTION_QUOTE_MAX_AGE_SECONDS', '180'))
        self.max_spread_percent = float(os.getenv('BABY_EXECUTION_MAX_SPREAD_PERCENT', '2.0'))

    def _validate(self, q: dict[str, Any]) -> dict[str, Any]:
        out = dict(q or {})
        price = _num(out.get('price'))
        bid = _num(out.get('bid'))
        ask = _num(out.get('ask'))
        ts = _parse_ts(out.get('timestamp') or out.get('as_of'))
        now = datetime.now(timezone.utc)
        age = max(0.0, (now - ts).total_seconds()) if ts else None
        issues: list[str] = []

        if price is None or price <= 0:
            issues.append('MISSING_OR_INVALID_PRICE')
        if ts is None:
            issues.append('MISSING_TIMESTAMP')
        elif age is not None and age > self.max_age_seconds:
            issues.append('STALE_TIMESTAMP')

        spread_pct = None
        if bid is not None or ask is not None:
            if bid is None or bid <= 0:
                issues.append('INVALID_BID')
            if ask is None or ask <= 0:
                issues.append('INVALID_ASK')
            if bid is not None and ask is not None and bid > 0 and ask > 0:
                if ask < bid:
                    issues.append('CROSSED_QUOTE')
                else:
                    mid = (bid + ask) / 2.0
                    spread_pct = ((ask - bid) / mid * 100.0) if mid > 0 else None
                    if spread_pct is not None and spread_pct > self.max_spread_percent:
                        issues.append('WIDE_SPREAD')

        provider = str(out.get('provider') or out.get('source') or 'UNKNOWN').upper()
        quality = str(out.get('quality') or 'UNKNOWN').upper()
        provider_ok = provider == 'ALPACA_MARKET_DATA'
        quality_ok = quality in {'LIVE_IEX', 'LIVE', 'MARKET_DATA'}
        if not provider_ok:
            issues.append('NON_EXECUTION_PROVIDER')
        if not quality_ok:
            issues.append('NON_EXECUTION_QUALITY')

        out['age_seconds'] = round(age, 3) if age is not None else None
        out['spread_percent'] = round(spread_pct, 4) if spread_pct is not None else None
        out['validation_issues'] = list(dict.fromkeys(issues))
        out['execution_eligible'] = len(out['validation_issues']) == 0
        out['execution_grade'] = 'PASS' if out['execution_eligible'] else 'BLOCKED'
        out['authority'] = 'CURRENT_MARKET_EVIDENCE' if provider_ok else 'SECONDARY_REFERENCE_ONLY'
        return out

    def get(self, symbol: str) -> dict[str, Any]:
        symbol = (symbol or '').upper().strip()
        if not symbol:
            raise ValueError('symbol is required')
        alpaca_error = None
        try:
            q = self.alpaca.current_quote(symbol, feed='iex')
            return self._validate(q)
        except Exception as e:
            alpaca_error = str(e)

        q = self.fallback.get(symbol).__dict__
        q['fallback_reason'] = alpaca_error or 'Alpaca market data unavailable.'
        return self._validate(q)
