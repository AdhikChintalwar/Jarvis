from __future__ import annotations
import json, re, urllib.parse
from pathlib import Path
from typing import Any
from .alpaca_market import AlpacaMarketScreener

class BabyReadOnlyTools:
    """Read-only tool registry for Baby V9. No broker/order functions are exposed here."""
    def __init__(self, report_dir: Path):
        self.report_dir=Path(report_dir); self.market=AlpacaMarketScreener()

    def schemas(self)->list[dict[str,Any]]:
        return [
          {'name':'resolve_asset','description':'Resolve a US company name or ticker to an active Alpaca equity.','args':{'query':'string'}},
          {'name':'get_quote','description':'Get current US equity snapshot/quote from Alpaca market data.','args':{'symbol_or_company':'string'}},
          {'name':'get_company_profile','description':'Get Alpaca asset metadata for a company/ticker.','args':{'symbol_or_company':'string'}},
          {'name':'get_company_news','description':'Get recent Alpaca news for a company/ticker.','args':{'symbol_or_company':'string','limit':'integer 1-20'}},
          {'name':'get_market_news','description':'Get recent broad market news from Alpaca.','args':{'limit':'integer 1-20'}},
          {'name':'get_market_context','description':'Get current SPY/QQQ/DIA/IWM snapshots for broad US market context.','args':{}},
          {'name':'get_baby_research','description':'Read Baby production research already generated for a symbol.','args':{'symbol_or_company':'string'}},
          {'name':'screen_price','description':'Deterministically screen active/tradable US equities by current price range.','args':{'min_price':'number','max_price':'number','limit':'integer'}},
          {'name':'get_baby_capabilities','description':'Describe Baby authority boundaries and available research tools.','args':{}},
        ]

    def _resolve(self,x:str)->str:
        x=(x or '').strip()
        if re.fullmatch(r'[A-Za-z]{1,5}',x):
            r=self.market.resolve_company(x)
        else:r=self.market.resolve_company(x)
        if not r or not r.get('symbol'): raise ValueError(f'Could not uniquely resolve asset: {x}')
        return r['symbol'].upper()

    def call(self,name:str,args:dict|None=None)->dict[str,Any]:
        args=args or {}
        if name=='resolve_asset': return self.market.resolve_company(str(args.get('query') or '')) or {'resolution':'NOT_FOUND'}
        if name=='get_quote': return self.market.current_quote(self._resolve(str(args.get('symbol_or_company') or '')))
        if name=='get_company_profile':
            sym=self._resolve(str(args.get('symbol_or_company') or '')); a=self.market.asset(sym); return {'symbol':sym,'asset':a,'source':'Alpaca Assets API'}
        if name=='get_company_news':
            sym=self._resolve(str(args.get('symbol_or_company') or '')); return self.market.news(symbols=[sym],limit=int(args.get('limit') or 10))
        if name=='get_market_news': return self.market.news(limit=int(args.get('limit') or 12))
        if name=='get_market_context':
            syms=['SPY','QQQ','DIA','IWM']; return {'snapshots':{s:self.market.current_quote(s) for s in syms},'source':'Alpaca Market Data','feed':'IEX'}
        if name=='get_baby_research':
            sym=self._resolve(str(args.get('symbol_or_company') or '')); p=self.report_dir/f'{sym}.json'
            if not p.exists(): return {'symbol':sym,'research_status':'NOT_RESEARCHED','source':'Baby production research store'}
            return {'symbol':sym,'research_status':'READY','report':json.loads(p.read_text()),'source':'Baby production research store'}
        if name=='screen_price': return self.market.filter_price(float(args['min_price']),float(args['max_price']),int(args.get('limit') or 100))
        if name=='get_baby_capabilities': return {'name':'Baby','scope':['general conversation','investment education','current market quotes','market/company news','Baby production research','deterministic screening'],'authority':{'market_facts':'verified tool data','research_scores':'Baby deterministic engines','AI_scoring_authority':'0%','chat_execution_authority':'NONE','real_money_execution':'DISABLED'},'limitations':['IEX is not consolidated SIP','news availability depends on Alpaca entitlement','missing evidence remains UNKNOWN']}
        raise ValueError(f'Unknown/read-prohibited tool: {name}')
