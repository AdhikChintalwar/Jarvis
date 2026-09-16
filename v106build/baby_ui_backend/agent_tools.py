from __future__ import annotations
import json, re, urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from .alpaca_market import AlpacaMarketScreener
from .v10_intelligence import V10IntelligenceService

class BabyReadOnlyTools:
    """Read-only tool registry for Baby V9. No broker/order functions are exposed here."""
    def __init__(self, report_dir: Path):
        self.report_dir=Path(report_dir); self.market=AlpacaMarketScreener(); self.v10=V10IntelligenceService(self.report_dir)

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
          {'name':'get_full_investment_flow','description':'Get Baby deterministic full research-to-trade flow including decision, risk, trade setup, entry/invalidation/targets and exit policy.','args':{'symbol_or_company':'string'}},
          {'name':'get_trade_plan','description':'Get Baby production trade plan and deterministic exit policy for a researched symbol.','args':{'symbol_or_company':'string'}},
        ]

    def _resolve(self,x:str)->str:
        x=(x or '').strip()
        if re.fullmatch(r'[A-Za-z]{1,5}',x):
            r=self.market.resolve_company(x)
        else:r=self.market.resolve_company(x)
        if not r or not r.get('symbol'): raise ValueError(f'Could not uniquely resolve asset: {x}')
        return r['symbol'].upper()


    def _validate_quote(self, q:dict[str,Any])->dict[str,Any]:
        """Deterministic quote sanity/freshness layer. Never lets AI decide data quality."""
        q=dict(q or {})
        issues=[]
        bid=q.get('bid'); ask=q.get('ask'); price=q.get('price')
        try:
            if bid is not None and float(bid)<=0: issues.append('INVALID_BID')
        except Exception: issues.append('INVALID_BID')
        try:
            if ask is not None and float(ask)<=0: issues.append('INVALID_ASK')
        except Exception: issues.append('INVALID_ASK')
        try:
            if bid is not None and ask is not None and float(bid)>0 and float(ask)>0:
                if float(ask)<float(bid): issues.append('CROSSED_QUOTE')
                mid=(float(ask)+float(bid))/2
                spread_pct=((float(ask)-float(bid))/mid*100) if mid>0 else None
                q['spread_pct']=spread_pct
                if spread_pct is not None and spread_pct>float(__import__('os').getenv('BABY_QUOTE_MAX_SPREAD_PCT','3')):
                    issues.append('WIDE_SPREAD')
        except Exception: issues.append('INVALID_SPREAD')
        ts=q.get('timestamp'); age=None
        if ts:
            try:
                dt=datetime.fromisoformat(str(ts).replace('Z','+00:00')); age=max(0,(datetime.now(timezone.utc)-dt).total_seconds())
                q['age_seconds']=age
                if age>float(__import__('os').getenv('BABY_QUOTE_STALE_SECONDS','900')): issues.append('STALE_TIMESTAMP')
            except Exception: issues.append('INVALID_TIMESTAMP')
        if price is None: issues.append('MISSING_PRICE')
        feed=str(q.get('feed') or '').upper()
        if feed=='IEX': issues.append('IEX_PARTIAL_MARKET')
        severe={'INVALID_BID','INVALID_ASK','CROSSED_QUOTE','INVALID_SPREAD','MISSING_PRICE','INVALID_TIMESTAMP'}
        q['validation']={'status':'INVALID' if severe.intersection(issues) else ('REVIEW' if issues else 'PASS'),
                         'issues':issues,'authority':'DETERMINISTIC','freshness_seconds':age,
                         'feed_scope':'PARTIAL_MARKET' if feed=='IEX' else 'UNKNOWN_OR_CONSOLIDATED'}
        return q

    def call(self,name:str,args:dict|None=None)->dict[str,Any]:
        args=args or {}
        if name=='resolve_asset': return self.market.resolve_company(str(args.get('query') or '')) or {'resolution':'NOT_FOUND'}
        if name=='get_quote': return self._validate_quote(self.market.current_quote(self._resolve(str(args.get('symbol_or_company') or ''))))
        if name=='get_company_profile':
            sym=self._resolve(str(args.get('symbol_or_company') or '')); a=self.market.asset(sym); return {'symbol':sym,'asset':a,'source':'Alpaca Assets API'}
        if name=='get_company_news':
            sym=self._resolve(str(args.get('symbol_or_company') or '')); return self.market.news(symbols=[sym],limit=int(args.get('limit') or 10))
        if name=='get_market_news': return self.market.news(limit=int(args.get('limit') or 12))
        if name=='get_market_context':
            syms=['SPY','QQQ','DIA','IWM']; return {'snapshots':{s:self._validate_quote(self.market.current_quote(s)) for s in syms},'source':'Alpaca Market Data','feed':'IEX','validation':'DETERMINISTIC_PER_SNAPSHOT'}
        if name=='get_baby_research':
            sym=self._resolve(str(args.get('symbol_or_company') or '')); p=self.report_dir/f'{sym}.json'
            if not p.exists(): return {'symbol':sym,'research_status':'NOT_RESEARCHED','source':'Baby production research store'}
            return {'symbol':sym,'research_status':'READY','report':json.loads(p.read_text()),'source':'Baby production research store'}
        if name=='screen_price': return self.market.filter_price(float(args['min_price']),float(args['max_price']),int(args.get('limit') or 100))
        if name=='get_full_investment_flow':
            sym=self._resolve(str(args.get('symbol_or_company') or '')); q=self._validate_quote(self.market.current_quote(sym)); return self.v10.full_flow(sym,quote=q)
        if name=='get_trade_plan':
            sym=self._resolve(str(args.get('symbol_or_company') or '')); r=self.v10.load(sym); return {'symbol':sym,'trade_plan':r.get('trade_plan') if r.get('status')!='NOT_RESEARCHED' else None,'exit_policy':self.v10.exit_policy(r) if r.get('status')!='NOT_RESEARCHED' else None,'source':'Baby deterministic production research','authority':'DETERMINISTIC'}
        if name=='get_baby_capabilities': return {'name':'Baby','scope':['general conversation','investment education','current market quotes','market/company news','Baby production research','deterministic screening','full research-to-trade flow','deterministic entry/invalidation/targets','deterministic exit policy'],'authority':{'market_facts':'verified tool data','research_scores':'Baby deterministic engines','trade_levels':'Baby TradePlanAgent','AI_scoring_authority':'0%','chat_execution_authority':'NONE','real_money_execution':'DISABLED'},'limitations':['IEX is not consolidated SIP','news availability depends on Alpaca entitlement','missing evidence remains UNKNOWN','entry/exit levels are research/paper-trading scenarios until explicitly paper-executed']}
        raise ValueError(f'Unknown/read-prohibited tool: {name}')
