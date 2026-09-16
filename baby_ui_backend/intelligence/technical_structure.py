from __future__ import annotations
from .common import metric,stage,num
def build_technical(research):
 st=next((s for s in research.get('stages',[]) if s.get('id')=='technical'),{});src={m.get('key'):m for m in st.get('metrics',[]) if isinstance(m,dict)}
 val=lambda k:(src.get(k) or {}).get('value');ev=lambda k:(src.get(k) or {}).get('provenance') or []
 p,s20,s50,s200=map(num,(val('price'),val('sma20'),val('sma50'),val('sma200')));rsi=num(val('rsi14'));atr=num(val('atr14'));rv=num(val('rvol'))
 trend='UNKNOWN' if None in (p,s20,s50,s200) else ('BULLISH' if p>s20>s50>s200 else 'BEARISH' if p<s20<s50<s200 else 'MIXED');atrp=100*atr/p if p and atr else None;vr='UNKNOWN' if rv is None else ('EXPANDED' if rv>=1.5 else 'NORMAL' if rv>=.75 else 'QUIET')
 ms=[metric('trend_regime','Trend Regime',trend,status='PASS' if trend!='UNKNOWN' else 'UNKNOWN',formula='Price/SMA20/SMA50/SMA200 ordering',inputs={'price':p,'sma20':s20,'sma50':s50,'sma200':s200},evidence=ev('price')+ev('sma20')+ev('sma50')+ev('sma200')),metric('rsi14','RSI 14',rsi,evidence=ev('rsi14')),metric('atr_percent','ATR %',atrp,unit='%',formula='ATR14 / Price × 100',inputs={'atr14':atr,'price':p},evidence=ev('atr14')+ev('price')),metric('relative_volume','Relative Volume',rv,evidence=ev('rvol')),metric('volume_regime','Volume Regime',vr,status='PASS' if vr!='UNKNOWN' else 'UNKNOWN',evidence=ev('rvol'))]
 trade=research.get('trade_plan') or {};tev=[{'source':trade.get('market_data_source') or 'Production market history','authority':'SECONDARY_MARKET_DATA','as_of':trade.get('market_data_as_of'),'verified':False,'status':'DERIVED'}]
 for k,l in [('support_1','Support 1'),('support_2','Support 2'),('resistance_1','Resistance 1'),('resistance_2','Resistance 2')]:ms.append(metric(k,l,trade.get(k),evidence=tev))
 return stage('technical_v102','V10.2 Technical, Volume & Market-Structure Intelligence',ms,summary='Deterministic technical metrics with market-data lineage.')
