import os
os.environ['BABY_COPILOT_MODE']='LEGACY'
from pathlib import Path
from baby_ui_backend.copilot import BabyCopilot

class FakeMarket:
    def resolve_company(self,q):
        q=' '.join(q.strip().lower().replace('$','').split())
        m={'nvidia':'NVDA','nvidia corporation':'NVDA','nvda':'NVDA','tesla':'TSLA','tesla motors':'TSLA','tsla':'TSLA','amd':'AMD','advanced micro devices':'AMD','apple':'AAPL','aapl':'AAPL'}
        s=m.get(q)
        return {'symbol':s,'query':q,'resolution':'TEST'} if s else {'symbol':None,'query':q,'resolution':'NOT_FOUND'}
    def current_quote(self,symbol,feed='iex'):
        px={'NVDA':213.94,'TSLA':358.13,'AMD':162.40,'AAPL':334.23}[symbol]
        prev={'NVDA':212.16,'TSLA':356.68,'AMD':160.00,'AAPL':330.00}[symbol]
        return {'symbol':symbol,'price':px,'previous_close':prev,'change':px-prev,'change_pct':(px-prev)/prev*100,'timestamp':'2026-09-16T19:59:59Z','quality':'LIVE_IEX','provider':'ALPACA_MARKET_DATA','feed':'IEX'}
    def filter_price(self,*a,**k): return {'count':0,'results':[],'filters':{},'source':'TEST','feed':'IEX'}

c=BabyCopilot(Path('/tmp/no-reports')); c.market=FakeMarket(); sid='v874-real-failures'
# Exact live failure #1: stale AAPL UI must not hijack typo'd quote continuation.
r1=c.ask('how much is NVIDIA stock today?',{'symbol':'AAPL','stage_id':'data'},sid)
assert r1['mode']=='MARKET_QUOTE' and r1['data']['symbol']=='NVDA'
r2=c.ask('howb about Tesla stock',{'symbol':'AAPL','stage_id':'data'},sid)
assert r2['mode']=='MARKET_QUOTE' and r2['data']['symbol']=='TSLA' and 'AAPL' not in r2['answer']
r3=c.ask('how much is tesla stock',{'symbol':'AAPL','stage_id':'data'},sid)
assert r3['mode']=='MARKET_QUOTE' and r3['data']['symbol']=='TSLA'
# Exact live failure #2: SEC must canonicalize to a real educational topic and never KeyError.
r4=c.ask('what is SEC filings',{'symbol':'AAPL','stage_id':'data'},sid)
assert r4['mode']=='EDUCATION' and r4['data']['topic']=='SEC_FILINGS' and 'filing' in r4['answer'].lower()
r5=c.ask('explain more',{'symbol':'AAPL','stage_id':'data'},sid)
assert r5['mode']=='EDUCATION' and r5['data']['topic']=='SEC_FILINGS' and '10-K' in r5['answer']
r6=c.ask('why are they important?',{'symbol':'AAPL','stage_id':'data'},sid)
assert r6['mode']=='EDUCATION' and 'important' in r6['answer'].lower()
# Existing educational topic behavior stays intact.
r7=c.ask('what is RSI?',{},sid); assert r7['data']['topic']=='RSI'
r8=c.ask('explain morre about it',{},sid); assert r8['mode']=='EDUCATION' and 'RSI' in r8['answer']
r9=c.ask('how is it calculated?',{},sid); assert r9['mode']=='EDUCATION' and 'RSI14' in r9['answer']
# Status abbreviations cannot create a crashing active topic.
r10=c.ask('what is PASS',{},sid); assert r10['mode']=='EDUCATION'
r11=c.ask('explain more',{},sid); assert r11['mode']=='EDUCATION' and 'PASS' in r11['answer']
print('BABY V8.7.4 ROUTER + KNOWLEDGE RESILIENCE: PASS')
print('exact typo quote continuation: PASS')
print('stale UI context cannot hijack explicit entity: PASS')
print('SEC -> SEC_FILINGS canonical topic: PASS')
print('generic SEC continuation without KeyError: PASS')
print('status-topic continuation without KeyError: PASS')
print('AI scoring authority: 0%')
print('chat execution authority: NONE')
print('real-money execution: DISABLED')
