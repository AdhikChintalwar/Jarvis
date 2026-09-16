from __future__ import annotations
import asyncio, json, os
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from .glossary import GLOSSARY
from .store import AlertStore
from .notifications import NotificationEngine
from .quote_service import QuoteService
from .research_service import ResearchService
from .control_center import validation_summary, automations, scanner, system_status
from .paper_trading import PaperTradingService

app=FastAPI(title='Baby UI Gateway',version='8.3.0')
app.add_middleware(CORSMiddleware,allow_origins=['http://localhost:5173','http://127.0.0.1:5173'],allow_credentials=True,allow_methods=['*'],allow_headers=['*'])
store=AlertStore(); notifier=NotificationEngine(store=store); quote_service=QuoteService()
paper_service=PaperTradingService()
REPORT_DIR=Path(os.getenv('BABY_RESEARCH_REPORT_DIR','data/ui_research')); REPORT_DIR.mkdir(parents=True,exist_ok=True)
research_service=ResearchService(report_dir=REPORT_DIR,notifier=notifier)

@app.get('/')
def root(): return {'service':'BABY UI Gateway','version':'8.3.0','ui':'http://127.0.0.1:5173','docs':'/docs'}
@app.get('/api/health')
def health(): return {'status':'ok','version':'8.3.0','ai_scoring_authority':0.0,'real_money_execution':'DISABLED','quote_refresh_seconds':float(os.getenv('BABY_QUOTE_REFRESH_SECONDS','10'))}
@app.get('/api/glossary')
def glossary(): return GLOSSARY
@app.get('/api/research/{symbol}')
def research(symbol:str):
    symbol=symbol.upper(); p=REPORT_DIR/f'{symbol}.json'
    if not p.exists():
        return {'symbol':symbol,'research_status':'NOT_RESEARCHED','job':research_service.status(symbol)}
    data=json.loads(p.read_text()); data['research_status']='READY'; return data
@app.get('/api/research/{symbol}/status')
def research_status(symbol:str): return research_service.status(symbol)
@app.post('/api/research/{symbol}/run')
def run_research(symbol:str,force:bool=False):
    try: return research_service.start(symbol,force=force)
    except ValueError as e: raise HTTPException(400,str(e))
@app.get('/api/quote/{symbol}')
def quote(symbol:str): return quote_service.get(symbol.upper()).__dict__
@app.get('/api/alerts')
def alerts(limit:int=100): return store.list(min(max(limit,1),500))
@app.post('/api/alerts/test')
def test_alert(): return notifier.emit(dedupe_key='v8-test',title='BABY — Notification Test',message='Baby UI notification engine is connected.',severity='NOTICE',force=True)


@app.get('/api/control/status')
def control_status(): return system_status()
@app.get('/api/backtests/v7_5')
def backtest_v75(): return validation_summary()
@app.get('/api/portfolio/paper')
def paper():
    base=paper_service.snapshot({})
    quotes={}
    for pos in base.get('positions',[]):
        try: quotes[pos['symbol']]=quote_service.get(pos['symbol']).__dict__
        except Exception: quotes[pos['symbol']]={}
    return paper_service.snapshot(quotes)

@app.post('/api/portfolio/paper/orders')
def paper_submit(payload:dict):
    try:
        return paper_service.submit_order(payload.get('symbol',''),payload.get('side',''),payload.get('quantity',0),payload.get('order_type','MARKET'),payload.get('limit_price'),payload.get('note'))
    except ValueError as e: raise HTTPException(400,str(e))

@app.post('/api/portfolio/paper/orders/{order_id}/execute')
def paper_execute(order_id:str):
    import sqlite3
    with sqlite3.connect(paper_service.path) as db:
        row=db.execute('SELECT symbol FROM paper_orders WHERE id=?',(order_id,)).fetchone()
    if not row: raise HTTPException(404,'paper order not found')
    q=quote_service.get(row[0]).__dict__
    try: result=paper_service.execute(order_id,q)
    except (ValueError,KeyError) as e: raise HTTPException(400,str(e))
    if result.get('status')=='FILLED':
        notifier.emit(dedupe_key=f"paper-fill-{order_id}",title=f"BABY — Paper {result['side']} filled",message=f"{result['symbol']} {result['filled_quantity']} @ {result['average_fill_price']:.2f} — simulation only",severity='NOTICE',force=True)
    return result

@app.post('/api/portfolio/paper/reset')
def paper_reset(payload:dict|None=None):
    payload=payload or {}
    try:return paper_service.reset(payload.get('starting_cash'))
    except ValueError as e:raise HTTPException(400,str(e))
@app.get('/api/automations')
def automation_list(): return automations()
@app.get('/api/scanner/latest')
def scanner_latest(): return scanner()

@app.websocket('/ws/market/{symbol}')
async def market_ws(ws:WebSocket,symbol:str):
    await ws.accept(); symbol=symbol.upper(); refresh=max(5.0,float(os.getenv('BABY_QUOTE_REFRESH_SECONDS','10')))
    try:
        while True:
            await ws.send_json(quote_service.get(symbol).__dict__); await asyncio.sleep(refresh)
    except (WebSocketDisconnect,RuntimeError): return
