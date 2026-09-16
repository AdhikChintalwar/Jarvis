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
from .research_orchestrator import ResearchOrchestrator, ResearchOrchestrationError
from .control_center import validation_summary, automations, scanner, system_status
from .paper_trading import PaperTradingService
from .proposal_service import PaperProposalService
from .alpaca_broker import AlpacaPaperBroker, CONFIRMATION_PHRASE

app=FastAPI(title='Baby UI Gateway',version='8.7.1')
app.add_middleware(CORSMiddleware,allow_origins=['http://localhost:5173','http://127.0.0.1:5173'],allow_credentials=True,allow_methods=['*'],allow_headers=['*'])
store=AlertStore(); notifier=NotificationEngine(store=store); quote_service=QuoteService()
paper_service=PaperTradingService()
alpaca_broker=AlpacaPaperBroker()
proposal_service=PaperProposalService(base_risk_percent=float(os.getenv('BABY_PAPER_RISK_PERCENT','0.5')),max_position_percent=float(os.getenv('BABY_PAPER_MAX_POSITION_PERCENT','10')))
REPORT_DIR=Path(os.getenv('BABY_RESEARCH_REPORT_DIR','data/ui_research')); REPORT_DIR.mkdir(parents=True,exist_ok=True)
research_service=ResearchService(report_dir=REPORT_DIR,notifier=notifier,account_size_provider=lambda: paper_service.snapshot({}).get('account',{}).get('equity',paper_service.starting_cash))
research_orchestrator=ResearchOrchestrator(research_service,REPORT_DIR)

@app.get('/')
def root(): return {'service':'BABY UI Gateway','version':'8.7.3','ui':'http://127.0.0.1:5173','docs':'/docs'}
@app.get('/api/health')
def health(): return {'status':'ok','version':'8.7.3','ai_scoring_authority':0.0,'real_money_execution':'DISABLED','quote_refresh_seconds':float(os.getenv('BABY_QUOTE_REFRESH_SECONDS','10'))}
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


def _paper_snapshot_with_quotes():
    base=paper_service.snapshot({}); quotes={}
    for pos in base.get('positions',[]):
        try: quotes[pos['symbol']]=quote_service.get(pos['symbol']).__dict__
        except Exception: quotes[pos['symbol']]={}
    return paper_service.snapshot(quotes)

@app.get('/api/research/{symbol}/paper-proposal')
def paper_proposal(symbol:str):
    symbol=symbol.upper(); p=REPORT_DIR/f'{symbol}.json'
    if not p.exists(): raise HTTPException(404,'Run Baby research before requesting a paper proposal.')
    research=json.loads(p.read_text())
    q=quote_service.get(symbol).__dict__
    return proposal_service.build(symbol,research,q,_paper_snapshot_with_quotes())

@app.post('/api/research/{symbol}/paper-proposal/order')
def paper_proposal_order(symbol:str):
    proposal=paper_proposal(symbol)
    if not proposal.get('eligible'):
        raise HTTPException(409,proposal.get('reason') or 'Paper proposal is not eligible.')
    qty=proposal.get('proposed_quantity')
    if not qty: raise HTTPException(409,'No positive paper quantity was produced.')
    note=(f"BABY V8.5 deterministic proposal | decision={proposal['research_decision']} | "
          f"setup={proposal['setup_status']} | risk={proposal['risk_level']} | "
          f"invalidation={proposal['invalidation']} | target1={proposal['target_1']} | "
          f"AI authority=0 | REAL MONEY DISABLED")
    order=paper_service.submit_order(symbol,'BUY',qty,'MARKET',None,note)
    return {'proposal':proposal,'order':order,'execution':'PENDING_USER_PAPER_EXECUTION'}



# ---- Alpaca PAPER execution bridge -------------------------------------------------
# Live trading is deliberately not exposed by V8.6. The broker adapter hard-codes
# paper=True and every submit call requires the exact explicit confirmation phrase.
@app.get('/api/broker/alpaca/status')
def alpaca_status():
    return alpaca_broker.status()

@app.get('/api/broker/alpaca/positions')
def alpaca_positions():
    try: return {'environment':'PAPER','positions':alpaca_broker.positions()}
    except Exception as e: raise HTTPException(503,str(e))

@app.get('/api/broker/alpaca/orders')
def alpaca_orders(limit:int=100):
    try: return {'environment':'PAPER','orders':alpaca_broker.orders(limit)}
    except Exception as e: raise HTTPException(503,str(e))

@app.post('/api/broker/alpaca/orders')
def alpaca_submit(payload:dict):
    try:
        order=alpaca_broker.submit_confirmed_order(
            symbol=payload.get('symbol',''), side=payload.get('side',''),
            quantity=payload.get('quantity',0), order_type=payload.get('order_type','MARKET'),
            limit_price=payload.get('limit_price'), confirmation=payload.get('confirmation',''),
        )
        notifier.emit(dedupe_key=f"alpaca-paper-{order.get('id')}",title='BABY — Alpaca PAPER order submitted',message=f"{order.get('side')} {order.get('qty')} {order.get('symbol')} · PAPER ONLY",severity='NOTICE',force=True)
        return {'order':order,'environment':'PAPER','real_money_execution':'DISABLED'}
    except PermissionError as e: raise HTTPException(409,str(e))
    except ValueError as e: raise HTTPException(400,str(e))
    except Exception as e: raise HTTPException(503,str(e))

@app.delete('/api/broker/alpaca/orders/{order_id}')
def alpaca_cancel(order_id:str):
    try:return alpaca_broker.cancel(order_id)
    except Exception as e:raise HTTPException(503,str(e))

def _alpaca_research_proposal(symbol:str):
    symbol=symbol.upper(); p=REPORT_DIR/f'{symbol}.json'
    if not p.exists(): raise HTTPException(404,'Run Baby research before requesting an Alpaca paper proposal.')
    research=json.loads(p.read_text()); q=quote_service.get(symbol).__dict__; status=alpaca_broker.status()
    if not status.get('connected'): raise HTTPException(503,'Alpaca PAPER is not connected.')
    portfolio={'account':{'equity':status.get('equity'),'cash':status.get('cash'),'buying_power':status.get('buying_power')}}
    return proposal_service.build(symbol,research,q,portfolio)

@app.get('/api/research/{symbol}/alpaca-paper-proposal')
def alpaca_research_proposal(symbol:str):
    return _alpaca_research_proposal(symbol)

@app.post('/api/research/{symbol}/alpaca-paper-order')
def alpaca_from_research(symbol:str,payload:dict):
    # Recompute from production research + CURRENT Alpaca PAPER equity/cash at submission time.
    # Quantity supplied by the browser is deliberately ignored.
    proposal=_alpaca_research_proposal(symbol)
    if not proposal.get('eligible'):
        raise HTTPException(409,proposal.get('reason') or 'Current production setup is not eligible.')
    qty=proposal.get('proposed_quantity')
    if not qty: raise HTTPException(409,'No positive deterministic quantity was produced.')
    try:
        order=alpaca_broker.submit_confirmed_order(symbol=symbol.upper(),side='BUY',quantity=qty,order_type='MARKET',confirmation=payload.get('confirmation',''))
        return {'proposal':proposal,'order':order,'environment':'ALPACA_PAPER','real_money_execution':'DISABLED','quantity_source':'SERVER_DETERMINISTIC_PROPOSAL'}
    except PermissionError as e: raise HTTPException(409,str(e))
    except Exception as e: raise HTTPException(503,str(e))

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

# ---- V8.7 explainability + Ask Baby -----------------------------------------------
from .research_knowledge import STAGE_KNOWLEDGE, STATUS_LEGEND, ABBREVIATIONS, stage_explanation
from .copilot import BabyCopilot
copilot=BabyCopilot(REPORT_DIR)

@app.get('/api/research/legend/all')
def research_legend():
    return {'stages':STAGE_KNOWLEDGE,'statuses':STATUS_LEGEND,'abbreviations':ABBREVIATIONS,'principles':['Missing evidence stays UNKNOWN; it is not automatically bearish.','Primary evidence remains authoritative; independent providers are validation.','AI scoring authority is 0%.','AI execution authority is NONE.','Real-money execution is disabled.']}

@app.get('/api/research/{symbol}/explain/{stage_id}')
def explain_stage(symbol:str,stage_id:str):
    if stage_id not in STAGE_KNOWLEDGE: raise HTTPException(404,'Unknown research stage.')
    p=REPORT_DIR/f'{symbol.upper()}.json'; report=json.loads(p.read_text()) if p.exists() else {}
    stage=next((x for x in report.get('stages',[]) if x.get('id')==stage_id),None)
    return stage_explanation(stage_id,stage)


@app.get('/api/copilot/status')
def copilot_status():
    return copilot.runtime_status()

@app.post('/api/copilot/chat')
def copilot_chat(payload:dict):
    try:return copilot.ask(str(payload.get('message') or ''),payload.get('context') or {},str(payload.get('session_id') or ''))
    except ValueError as e:raise HTTPException(400,str(e))
    except RuntimeError as e:raise HTTPException(503,str(e))
    except Exception as e:raise HTTPException(500,f'Copilot tool failed: {e}')


# --- V10 Investment Intelligence -------------------------------------------------
from .v10_intelligence import V10IntelligenceService
v10_intelligence=V10IntelligenceService(REPORT_DIR)

def _v10_build_full_flow(symbol:str, *, force:bool=False):
    symbol=symbol.upper()
    try:
        cache=research_orchestrator.ensure(symbol,force=force)
    except ValueError as e:
        raise HTTPException(400,str(e))
    except ResearchOrchestrationError as e:
        raise HTTPException(503,detail=e.to_dict())
    p=REPORT_DIR/f'{symbol}.json'
    if not p.exists():
        raise HTTPException(503,detail={'status':'RESEARCH_FAILED','symbol':symbol,'stage':'ARTIFACT_MISSING','error':'Research orchestration completed without a persisted artifact.'})
    try:
        research=json.loads(p.read_text())
    except Exception as e:
        raise HTTPException(503,detail={'status':'RESEARCH_FAILED','symbol':symbol,'stage':'ARTIFACT_INVALID','error':str(e)})
    # Fetch one quote exactly once for the current-state gate and proposal.
    q=quote_service.get(symbol).__dict__
    portfolio=_paper_snapshot_with_quotes()
    proposal=proposal_service.build(symbol,research,q,portfolio)
    flow=v10_intelligence.full_flow(symbol,quote=q,portfolio=portfolio,proposal=proposal)
    flow['research_cache']=cache
    flow['orchestration']={
        'status':'COMPLETE','symbol':symbol,'research_action':cache.get('action'),
        'single_quote_snapshot':True,'auto_research':True,
        'note':'GET remains backward-compatible; POST run-full-flow is the canonical mutating orchestration endpoint.'
    }
    return flow

@app.get('/api/v10/research/{symbol}/full-flow')
def v10_full_flow(symbol:str,auto_research:bool=True,force:bool=False):
    if not auto_research:
        state=research_orchestrator.inspect(symbol)
        if state.status!='FRESH':
            raise HTTPException(409,detail={'status':'RESEARCH_REQUIRED','cache':state.to_dict(),'hint':'Use POST /api/v10/research/{symbol}/run-full-flow or auto_research=true.'})
    return _v10_build_full_flow(symbol,force=force)

@app.post('/api/v10/research/{symbol}/run-full-flow')
def v10_run_full_flow(symbol:str,force:bool=False):
    return _v10_build_full_flow(symbol,force=force)

@app.get('/api/v10/research/{symbol}/cache-status')
def v10_cache_status(symbol:str):
    try:return research_orchestrator.inspect(symbol).to_dict()
    except ValueError as e:raise HTTPException(400,str(e))

@app.get('/api/v10/research/{symbol}/exit-policy')
def v10_exit_policy(symbol:str,auto_research:bool=True):
    symbol=symbol.upper()
    if auto_research:
        try:research_orchestrator.ensure(symbol)
        except ResearchOrchestrationError as e:raise HTTPException(503,detail=e.to_dict())
    r=v10_intelligence.load(symbol)
    if r.get('status')=='NOT_RESEARCHED': raise HTTPException(404,'Research is unavailable for exit-policy evaluation.')
    q=quote_service.get(symbol).__dict__
    snapshot=__import__('baby_ui_backend.v10_intelligence',fromlist=['canonical_market_snapshot']).canonical_market_snapshot(symbol,r,q)
    return v10_intelligence.exit_policy(r,snapshot)
