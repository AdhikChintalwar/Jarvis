from __future__ import annotations

def secondary_profile(symbol):
    """Secondary valuation inputs only. Never upgrades SEC primary facts."""
    try:
        import yfinance as yf
        t=yf.Ticker(symbol)
        fi=dict(t.fast_info or {})
        info={}
        try: info=t.info or {}
        except Exception: pass
        qt=str(info.get('quoteType') or '').upper()
        asset='ETF' if qt=='ETF' else ('EQUITY' if qt in {'EQUITY','STOCK'} else qt or 'UNKNOWN')
        return {'symbol':symbol.upper(),'asset_type':asset,'quote_type':qt,'sector':info.get('sector'),'industry':info.get('industry'),
                'market_cap':fi.get('market_cap') or info.get('marketCap'),
                'shares_outstanding':info.get('sharesOutstanding'),
                'source':'Yahoo Finance via yfinance','authority':'SECONDARY','verified':False}
    except Exception as e:
        return {'symbol':symbol.upper(),'source':'Yahoo Finance via yfinance','authority':'SECONDARY','error':str(e)}
