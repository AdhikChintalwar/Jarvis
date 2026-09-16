from __future__ import annotations
from .common import metric,stage,num,safe_div

def _vals(research):
 st=next((s for s in research.get('stages',[]) if s.get('id')=='technical'),{})
 return {m.get('key'):m.get('value') for m in st.get('metrics',[]) if isinstance(m,dict)}
def build_technical(research):
 v=_vals(research); p=num(v.get('price')); s20=num(v.get('sma20')); s50=num(v.get('sma50')); s200=num(v.get('sma200')); rsi=num(v.get('rsi14')); atr=num(v.get('atr14')); rv=num(v.get('rvol'))
 trend='UNKNOWN'
 if None not in (p,s20,s50,s200): trend='BULLISH' if p>s20>s50>s200 else ('BEARISH' if p<s20<s50<s200 else 'MIXED')
 atrp=(100*atr/p) if p and atr else None
 volume_regime='UNKNOWN' if rv is None else ('EXPANDED' if rv>=1.5 else 'NORMAL' if rv>=0.75 else 'QUIET')
 ms=[metric('trend_regime','Trend Regime',trend,status='PASS' if trend!='UNKNOWN' else 'UNKNOWN',formula='Price/SMA20/SMA50/SMA200 ordering',inputs={'price':p,'sma20':s20,'sma50':s50,'sma200':s200}),
 metric('rsi14','RSI 14',rsi),metric('atr_percent','ATR %',atrp,unit='%',formula='ATR14 / Price × 100',inputs={'atr14':atr,'price':p}),metric('relative_volume','Relative Volume',rv,formula='Current volume / reference average'),metric('volume_regime','Volume Regime',volume_regime,status='PASS' if volume_regime!='UNKNOWN' else 'UNKNOWN')]
 trade=research.get('trade_plan') or {}; ms += [metric('support_1','Support 1',trade.get('support_1')),metric('support_2','Support 2',trade.get('support_2')),metric('resistance_1','Resistance 1',trade.get('resistance_1')),metric('resistance_2','Resistance 2',trade.get('resistance_2'))]
 return stage('technical_v102','V10.2 Technical, Volume & Market-Structure Intelligence',ms,summary='Deterministic trend, volatility, volume regime and production structure levels. No LLM-created levels.')
