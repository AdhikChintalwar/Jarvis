from __future__ import annotations
import json, os, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(dotenv_path=PROJECT_ROOT / '.env', override=False)
from typing import Any

class AlpacaMarketScreener:
    """Read-only Alpaca market-data helper. Never submits orders."""
    def __init__(self):
        self.key=os.getenv('ALPACA_PAPER_API_KEY') or os.getenv('APCA_API_KEY_ID')
        self.secret=os.getenv('ALPACA_PAPER_SECRET_KEY') or os.getenv('APCA_API_SECRET_KEY')
    def _get(self,url:str):
        if not self.key or not self.secret: raise RuntimeError('Alpaca paper credentials are not configured.')
        req=urllib.request.Request(url,headers={'APCA-API-KEY-ID':self.key,'APCA-API-SECRET-KEY':self.secret,'User-Agent':'BabyInvestor/8.7'})
        with urllib.request.urlopen(req,timeout=30) as r:return json.loads(r.read().decode())
    def active_assets(self)->list[dict[str,Any]]:
        data=self._get('https://paper-api.alpaca.markets/v2/assets?status=active&asset_class=us_equity')
        return [x for x in data if x.get('tradable') and x.get('symbol')]
    def snapshots(self,symbols:list[str],feed:str='iex')->dict[str,Any]:
        out={}
        for i in range(0,len(symbols),200):
            batch=symbols[i:i+200]
            q=urllib.parse.urlencode({'symbols':','.join(batch),'feed':feed})
            d=self._get('https://data.alpaca.markets/v2/stocks/snapshots?'+q)
            out.update(d.get('snapshots',d) if isinstance(d,dict) else {})
        return out

    def resolve_company(self, query:str)->dict[str,Any]|None:
        """Resolve a user company/ticker reference against Alpaca's active US-equity universe.

        Exact ticker wins, then exact/normalized company-name matches, then conservative
        prefix/contains matching. Ambiguous matches are returned as unresolved.
        """
        raw=(query or '').strip(); norm=' '.join(raw.lower().replace('&',' and ').split())
        if not raw: return None
        aliases={
            'nvidia':'NVDA','nvidia corporation':'NVDA','nvda':'NVDA',
            'apple':'AAPL','apple inc':'AAPL','aapl':'AAPL',
            'microsoft':'MSFT','msft':'MSFT','amazon':'AMZN','amazon.com':'AMZN','amzn':'AMZN',
            'alphabet':'GOOGL','google':'GOOGL','googl':'GOOGL','meta':'META','meta platforms':'META',
            'tesla':'TSLA','tsla':'TSLA','amd':'AMD','advanced micro devices':'AMD',
            'broadcom':'AVGO','avgo':'AVGO','crowdstrike':'CRWD','crwd':'CRWD'
        }
        if norm in aliases:
            sym=aliases[norm]; return {'symbol':sym,'query':raw,'resolution':'ALIAS'}
        assets=self.active_assets()
        upper=raw.upper()
        exact_symbol=[a for a in assets if a.get('symbol','').upper()==upper]
        if exact_symbol:
            a=exact_symbol[0]; return {'symbol':a['symbol'],'name':a.get('name'),'query':raw,'resolution':'EXACT_TICKER'}
        def clean_name(x):
            x=(x or '').lower().replace('&',' and ')
            for suffix in [' corporation',' corp.',' corp',' incorporated',' inc.',' inc',' plc',' ltd.',' ltd',' holdings',' holding company']:
                if x.endswith(suffix): x=x[:-len(suffix)]
            return ' '.join(x.split())
        exact=[a for a in assets if clean_name(a.get('name'))==norm]
        if len(exact)==1:
            a=exact[0]; return {'symbol':a['symbol'],'name':a.get('name'),'query':raw,'resolution':'EXACT_NAME'}
        candidates=[a for a in assets if norm and (clean_name(a.get('name')).startswith(norm) or norm in clean_name(a.get('name')))]
        if len(candidates)==1:
            a=candidates[0]; return {'symbol':a['symbol'],'name':a.get('name'),'query':raw,'resolution':'UNIQUE_NAME'}
        return {'symbol':None,'query':raw,'resolution':'AMBIGUOUS' if candidates else 'NOT_FOUND','candidates':[{'symbol':a.get('symbol'),'name':a.get('name')} for a in candidates[:8]]}

    def current_quote(self, symbol:str, feed:str='iex')->dict[str,Any]:
        symbol=(symbol or '').upper().strip()
        if not symbol: raise ValueError('symbol is required')
        q=urllib.parse.urlencode({'feed':feed})
        d=self._get(f'https://data.alpaca.markets/v2/stocks/{urllib.parse.quote(symbol)}/snapshot?'+q)
        snap=d.get('snapshot',d) if isinstance(d,dict) else {}
        trade=snap.get('latestTrade') or {}; quote=snap.get('latestQuote') or {}; daily=snap.get('dailyBar') or {}; prev=snap.get('prevDailyBar') or {}
        price=trade.get('p') or daily.get('c')
        previous_close=prev.get('c')
        price=float(price) if price is not None else None
        previous_close=float(previous_close) if previous_close is not None else None
        change=(price-previous_close) if price is not None and previous_close not in (None,0) else None
        pct=(change/previous_close*100.0) if change is not None and previous_close else None
        ts=trade.get('t') or quote.get('t') or daily.get('t') or datetime.now(timezone.utc).isoformat()
        return {'symbol':symbol,'price':price,'change':change,'change_pct':pct,'previous_close':previous_close,
                'bid':quote.get('bp'),'ask':quote.get('ap'),'day_high':daily.get('h'),'day_low':daily.get('l'),'volume':daily.get('v'),
                'timestamp':ts,'quality':'LIVE_IEX' if feed=='iex' else 'MARKET_DATA','provider':'ALPACA_MARKET_DATA','feed':feed.upper(),
                'note':'IEX is an exchange-specific feed and is not the full consolidated SIP market feed.' if feed=='iex' else None}
    def asset(self, symbol:str)->dict[str,Any]:
        symbol=(symbol or '').upper().strip()
        if not symbol: raise ValueError('symbol is required')
        return self._get('https://paper-api.alpaca.markets/v2/assets/'+urllib.parse.quote(symbol))

    def news(self, symbols:list[str]|None=None, limit:int=10)->dict[str,Any]:
        params={'limit':max(1,min(int(limit),50)),'sort':'desc','include_content':'false'}
        if symbols: params['symbols']=','.join([str(x).upper() for x in symbols])
        q=urllib.parse.urlencode(params)
        d=self._get('https://data.alpaca.markets/v1beta1/news?'+q)
        rows=[]
        for x in (d.get('news') or []):
            rows.append({'id':x.get('id'),'headline':x.get('headline'),'summary':x.get('summary'),'author':x.get('author'),'source':x.get('source'),'created_at':x.get('created_at'),'updated_at':x.get('updated_at'),'symbols':x.get('symbols') or [],'url':x.get('url')})
        return {'news':rows,'count':len(rows),'source':'Alpaca News API','retrieval':'CURRENT','symbols':symbols or []}

    def filter_price(self,min_price:float,max_price:float,limit:int=100)->dict[str,Any]:
        if min_price<0 or max_price<=0 or min_price>max_price: raise ValueError('Invalid price range.')
        assets=self.active_assets(); symbols=[x['symbol'] for x in assets]
        snaps=self.snapshots(symbols)
        rows=[]
        for a in assets:
            s=a['symbol']; snap=snaps.get(s) or {}; trade=snap.get('latestTrade') or {}; daily=snap.get('dailyBar') or {}
            p=trade.get('p') or daily.get('c')
            try:p=float(p)
            except Exception:continue
            if min_price<=p<=max_price:
                rows.append({'symbol':s,'name':a.get('name'),'price':p,'exchange':a.get('exchange'),'tradable':bool(a.get('tradable')),'volume':daily.get('v'),'data_feed':'IEX','source':'Alpaca Market Data'})
        rows.sort(key=lambda x:(x['price'],x['symbol']))
        return {'filters':{'min_price':min_price,'max_price':max_price},'count':len(rows),'results':rows[:max(1,min(int(limit),250))],'source':'Alpaca Market Data','feed':'IEX','note':'Price filtering uses the Alpaca IEX feed available to paper-only/basic access; it is not full SIP coverage.'}
