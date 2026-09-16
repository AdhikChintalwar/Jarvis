from __future__ import annotations
from .sec_fundamentals import SecFundamentalProvider,build_fundamentals
from .technical_structure import build_technical
from .events import build_events
from .macro_sector import build_macro
from .valuation import build_valuation
from .institutional_options import build_institutional_options
from .market_profile import secondary_profile
from .live_context import LiveContextProvider

class V106IntelligencePlatform:
 def __init__(self,sec_provider=None,live_provider=None): self.sec=sec_provider or SecFundamentalProvider(); self.live=live_provider or LiveContextProvider()
 def build(self,symbol,research,*,news=None,market_context=None,profile=None,options=None,institutional=None,flow=None):
  warnings=[]
  if news is None: news=self.live.news(symbol)
  if market_context is None: market_context=self.live.market_context()
  try:facts=self.sec.companyfacts(symbol)
  except Exception as e:facts=None; warnings.append(f'SEC Company Facts unavailable: {e}')
  fundamentals=build_fundamentals(symbol,facts)
  technical=build_technical(research)
  events=build_events(symbol,news,research)
  profile=profile or secondary_profile(symbol)
  macro=build_macro(research,market_context,profile)
  profile=profile or {}; price=(research.get('trade_plan') or {}).get('current_price')
  valuation=build_valuation(research,fundamentals,profile.get('market_cap'),price,profile.get('shares_outstanding'))
  inst=build_institutional_options(options,institutional,flow)
  stages=[fundamentals,technical,events,macro,valuation,inst]
  return {'symbol':symbol.upper(),'status':'READY','schema_version':'10.6','stages':stages,'warnings':warnings,
          'authority':{'PRIMARY_FACTS':'SEC/XBRL','DERIVED_METRICS':'BABY_DETERMINISTIC','NEWS':'ATTRIBUTED_SOURCE','LLM_FACT_AUTHORITY':'NONE','LLM_SCORING_AUTHORITY':'0%','LLM_EXECUTION_AUTHORITY':'NONE','REAL_MONEY':'DISABLED'},
          'limitations':['Options/order-flow remain UNKNOWN without a verified feed.','Reverse DCF is a scenario model, not an objective fair value.','News headlines do not establish causality.']}
