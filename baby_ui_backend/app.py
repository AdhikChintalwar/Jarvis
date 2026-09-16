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
from .control_center import validation_summary, paper_portfolio, automations, scanner, system_status

app=FastAPI(title='Baby UI Gateway',version='8.2.0')
app.add_middleware(CORSMiddleware,allow_origins=['http://localhost:5173','http://127.0.0.1:5173'],allow_credentials=True,allow_methods=['*'],allow_headers=['*'])
store=AlertStore(); notifier=NotificationEngine(store=store); quote_service=QuoteService()
REPORT_DIR=Path(os.getenv('BABY_RESEARCH_REPORT_DIR','data/ui_research')); REPORT_DIR.mkdir(parents=True,exist_ok=True)
research_service=ResearchService(report_dir=REPORT_DIR,notifier=notifier)

@app.get('/')
def root(): return {'service':'BABY UI Gateway','version':'8.2.0','ui':'http://127.0.0.1:5173','docs':'/docs'}
@app.get('/api/health')
def health(): return {'status':'ok','version':'8.2.0','ai_scoring_authority':0.0,'real_money_execution':'DISABLED','quote_refresh_seconds':float(os.getenv('BABY_QUOTE_REFRESH_SECONDS','10'))}
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
def paper(): return paper_portfolio()
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
