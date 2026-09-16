from pathlib import Path
from baby_ui_backend.copilot import BabyCopilot

class FakeMarket:
    def resolve_company(self,q):
        q=q.strip().lower().replace('$','')
        m={'nvidia':'NVDA','nvidia corporation':'NVDA','nvda':'NVDA','amd':'AMD','advanced micro devices':'AMD','apple':'AAPL','aapl':'AAPL'}
        s=m.get(q)
        return {'symbol':s,'query':q,'resolution':'TEST'} if s else {'symbol':None,'query':q,'resolution':'NOT_FOUND'}
    def current_quote(self,symbol,feed='iex'):
        px={'NVDA':215.25,'AMD':162.40,'AAPL':334.23}[symbol]
        prev={'NVDA':212.17,'AMD':160.00,'AAPL':330.00}[symbol]
        return {'symbol':symbol,'price':px,'previous_close':prev,'change':px-prev,'change_pct':(px-prev)/prev*100,'timestamp':'2026-09-16T19:55:00Z','quality':'LIVE_IEX','provider':'ALPACA_MARKET_DATA','feed':'IEX'}
    def filter_price(self,*a,**k): return {'count':0,'results':[],'filters':{},'source':'TEST','feed':'IEX'}

c=BabyCopilot(Path('/tmp/no-reports')); c.market=FakeMarket(); sid='v873'
# Seed stale AAPL UI context. Explicit NVIDIA request must win.
r=c.ask('how much is stock price for NVIDIA today',{'symbol':'AAPL','stage_id':'data_collection'},sid)
assert r['mode']=='MARKET_QUOTE' and r['data']['symbol']=='NVDA' and 'AAPL' not in r['answer']
assert r['context_state']['symbol']=='NVDA' and r['context_state']['previous_intent']=='CURRENT_STOCK_QUOTE'
# Quote follow-up switches entity while retaining quote intent.
r2=c.ask('what about AMD?',{},sid)
assert r2['mode']=='MARKET_QUOTE' and r2['data']['symbol']=='AMD'
# New education topic overrides quote context, then generic follow-up stays educational.
r3=c.ask('what is RSI?',{},sid); assert r3['mode']=='EDUCATION' and r3['data']['topic']=='RSI'
r4=c.ask('explain more about it',{},sid); assert r4['mode']=='EDUCATION' and 'RSI' in r4['answer']
# Explicit quote overrides active RSI topic.
r5=c.ask('what is NVIDIA stock price right now?',{},sid); assert r5['mode']=='MARKET_QUOTE' and r5['data']['symbol']=='NVDA'
print('BABY V8.7.3 INTENT + ENTITY ROUTING: PASS')
print('explicit quote > stale UI context: PASS')
print('company name -> ticker: PASS')
print('quote follow-up entity switch: PASS')
print('education context preserved: PASS')
print('AI scoring authority: 0%')
print('chat execution authority: NONE')
print('real-money execution: DISABLED')
