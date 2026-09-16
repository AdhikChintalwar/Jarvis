from __future__ import annotations
from .common import metric,stage,num

def build_macro(research,market_context=None,profile=None):
 prod=next((s for s in research.get('stages',[]) if s.get('id')=='macro'),{})
 mc=market_context or {}; profile=profile or {}
 ms=[metric('production_macro_score','Production Macro Score',prod.get('score'),evidence=[]),metric('sector','Sector',profile.get('sector')),metric('industry','Industry',profile.get('industry')),
 metric('spy_change_percent','SPY Change %',mc.get('spy_change_percent'),unit='%'),metric('qqq_change_percent','QQQ Change %',mc.get('qqq_change_percent'),unit='%'),metric('vix','VIX',mc.get('vix')),metric('ten_year_yield','10Y Treasury Yield',mc.get('ten_year_yield'),unit='%')]
 return stage('macro_v104','V10.4 Macro, Sector & Cross-Asset Intelligence',ms,summary='Macro and cross-asset evidence is kept separate from company facts. Missing context remains UNKNOWN.')
