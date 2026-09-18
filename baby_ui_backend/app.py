from __future__ import annotations

from .history_service import HistoryService
from .operating_scheduler import BabyOperatingScheduler

import asyncio, json, os
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from .glossary import GLOSSARY
from .store import AlertStore
from .notifications import NotificationEngine
from .quote_service import QuoteService
from .execution_quote import ExecutionQuoteService
from .research_service import ResearchService
from .research_orchestrator import ResearchOrchestrator, ResearchOrchestrationError
from .control_center import validation_summary, automations, scanner, system_status
from .paper_trading import PaperTradingService
from .proposal_service import PaperProposalService
from .alpaca_broker import AlpacaPaperBroker, CONFIRMATION_PHRASE

app=FastAPI(title='Baby UI Gateway',version='10.6.0')
app.add_middleware(CORSMiddleware,allow_origins=['http://localhost:5173','http://127.0.0.1:5173'],allow_credentials=True,allow_methods=['*'],allow_headers=['*'])
store=AlertStore(); notifier=NotificationEngine(store=store); quote_service=QuoteService()
execution_quote_service=ExecutionQuoteService(fallback=quote_service)
paper_service=PaperTradingService()
alpaca_broker=AlpacaPaperBroker()
proposal_service=PaperProposalService(base_risk_percent=float(os.getenv('BABY_PAPER_RISK_PERCENT','0.5')),max_position_percent=float(os.getenv('BABY_PAPER_MAX_POSITION_PERCENT','10')),enforce_trade_quality=True,require_execution_grade=True,revalidate_setup=True)
REPORT_DIR=Path(os.getenv('BABY_RESEARCH_REPORT_DIR','data/ui_research')); REPORT_DIR.mkdir(parents=True,exist_ok=True)
research_service=ResearchService(report_dir=REPORT_DIR,notifier=notifier,account_size_provider=lambda: paper_service.snapshot({}).get('account',{}).get('equity',paper_service.starting_cash))
research_orchestrator=ResearchOrchestrator(research_service,REPORT_DIR)

@app.get('/')
def root(): return {'service':'BABY UI Gateway','version':'10.6.0','ui':'http://127.0.0.1:5173','docs':'/docs'}
@app.get('/api/health')
def health(): return {'status':'ok','version':'10.6.0','ai_scoring_authority':0.0,'real_money_execution':'DISABLED','quote_refresh_seconds':float(os.getenv('BABY_QUOTE_REFRESH_SECONDS','10'))}
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
    q=execution_quote_service.get(symbol)
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
    research=json.loads(p.read_text()); q=execution_quote_service.get(symbol); status=alpaca_broker.status()
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
from .intelligence import V106IntelligencePlatform
v10_intelligence=V10IntelligenceService(REPORT_DIR)
v106_intelligence=V106IntelligencePlatform()
from .v11 import V11InvestmentPlatform
v11_platform=V11InvestmentPlatform()

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
    # Fetch one independently validated execution/reference quote exactly once.
    # Secondary fallback remains display-only and can never authorize a proposal.
    q=execution_quote_service.get(symbol)
    portfolio=_paper_snapshot_with_quotes()
    proposal=proposal_service.build(symbol,research,q,portfolio)
    flow=v10_intelligence.full_flow(symbol,quote=q,portfolio=portfolio,proposal=proposal)
    try:
        flow['intelligence_v106']=v106_intelligence.build(symbol,research)
    except Exception as e:
        flow['intelligence_v106']={'symbol':symbol,'status':'PARTIAL','stages':[],'warnings':[f'V10.1-V10.6 intelligence enrichment failed safely: {e}'],'authority':{'LLM_SCORING_AUTHORITY':'0%','REAL_MONEY':'DISABLED'}}
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
    q=execution_quote_service.get(symbol)
    snapshot=__import__('baby_ui_backend.v10_intelligence',fromlist=['canonical_market_snapshot']).canonical_market_snapshot(symbol,r,q)
    return v10_intelligence.exit_policy(r,snapshot)


@app.get('/api/v10.6/research/{symbol}/intelligence')
def v106_research_intelligence(symbol:str,auto_research:bool=True,force:bool=False):
    symbol=symbol.upper()
    if auto_research:
        try: research_orchestrator.ensure(symbol,force=force)
        except ResearchOrchestrationError as e: raise HTTPException(503,detail=e.to_dict())
    p=REPORT_DIR/f'{symbol}.json'
    if not p.exists(): raise HTTPException(404,'Production research is unavailable.')
    research=json.loads(p.read_text())
    try:return v106_intelligence.build(symbol,research)
    except Exception as e:raise HTTPException(503,detail={'status':'INTELLIGENCE_FAILED','symbol':symbol,'error':str(e)})


# --- V11 Unified Thesis & Decision Intelligence --------------------------------
@app.get('/api/v11/research/{symbol}/analysis')
def v11_analysis(symbol:str,auto_research:bool=True,force:bool=False,record:bool=False):
    flow=_v10_build_full_flow(symbol,force=force) if auto_research else v10_intelligence.full_flow(symbol.upper(),quote=execution_quote_service.get(symbol.upper()),portfolio=_paper_snapshot_with_quotes())
    if flow.get('status')!='READY': raise HTTPException(409,detail=flow)
    research=json.loads((REPORT_DIR/f'{symbol.upper()}.json').read_text())
    v106=flow.get('intelligence_v106') or v106_intelligence.build(symbol.upper(),research)
    return v11_platform.build(symbol.upper(),research,v106,flow,record=record)

@app.post('/api/v11/research/{symbol}/run')
def v11_run(symbol:str,force:bool=False,record:bool=True):
    flow=_v10_build_full_flow(symbol,force=force)
    research=json.loads((REPORT_DIR/f'{symbol.upper()}.json').read_text())
    v106=flow.get('intelligence_v106') or v106_intelligence.build(symbol.upper(),research)
    return v11_platform.build(symbol.upper(),research,v106,flow,record=record)

# --- Baby Production Candidate ---------------------------------------------------
from investor.production import ProductionCandidate
from investor.production.monitoring import MonitoringStore
from investor.production.investment_monitor import InvestmentMonitorStore, InvestmentMonitorWorker
production_candidate=ProductionCandidate()
# V13 monitor bootstrap
investment_monitor_store = InvestmentMonitorStore()

def _monitor_decision(symbol: str):
    flow = _v10_build_full_flow(symbol, force=False)
    research = flow.get('research') or {}
    v106 = flow.get('v106') or flow.get('v10_6') or {}
    v11 = v11_platform.build(symbol, research, v106, flow.get('portfolio') or {})
    return production_candidate.decision.evaluate(v11, flow.get('portfolio') or {})

investment_monitor_worker = InvestmentMonitorWorker(
    investment_monitor_store,
    deep_evaluator=_monitor_decision,
    quote_getter=lambda symbol: execution_quote_service.get(symbol),
)
investment_monitor_worker.start()
# V13.1 services
history_service = HistoryService()
_baby_positions_getter = alpaca_positions
_baby_account_getter = alpaca_status

try:
    investment_monitor_worker.stop()
except Exception:
    pass
investment_monitor_worker = InvestmentMonitorWorker(
    investment_monitor_store,
    quote_getter=lambda s: execution_quote_service.get(s),
    deep_evaluator=_monitor_decision,
    positions_getter=_baby_positions_getter,
    account_getter=_baby_account_getter,
    sync_seconds=60,
    loop_seconds=15,
)
investment_monitor_worker.start()
baby_operating_scheduler = BabyOperatingScheduler(revalidate=_monitor_decision)
baby_operating_scheduler.start()


production_monitor=MonitoringStore()

@app.get('/api/production/health')
def production_health():
    return production_candidate.startup()

@app.post('/api/production/portfolio/gate')
def production_portfolio_gate(payload:dict):
    return production_candidate.portfolio.evaluate(
        equity=payload.get('equity'),cash=payload.get('cash'),positions=payload.get('positions') or [],
        candidate=payload.get('candidate') or {},proposed_notional=payload.get('proposed_notional'),proposed_risk=payload.get('proposed_risk'))

@app.post('/api/production/proposals/{symbol}')
def production_proposal(symbol:str,payload:dict):
    # Creates an auditable proposal only. It cannot execute a trade.
    return production_candidate.ledger.proposal(symbol.upper(),payload.get('proposal') or payload,payload.get('idempotency_key'))

@app.post('/api/production/positions/evaluate')
def production_position_evaluate(payload:dict):
    return production_candidate.positions.evaluate(payload.get('position') or {},payload.get('trade_plan') or {},payload.get('current') or {})

@app.post('/api/production/etf/{symbol}/thesis')
def production_etf_thesis(symbol:str,payload:dict):
    return production_candidate.etf.evaluate(symbol.upper(),payload.get('intelligence') or payload)


@app.post('/api/production/decision/{symbol}')
def production_decision(symbol:str,payload:dict):
    symbol=symbol.upper()
    force=bool(payload.get('force',False))
    record_v11=bool(payload.get('record_v11',True))

    flow=_v10_build_full_flow(symbol,force=force)
    p=REPORT_DIR/f'{symbol}.json'
    research=json.loads(p.read_text())
    v106=flow.get('intelligence_v106') or v106_intelligence.build(symbol,research)
    v11=v11_platform.build(symbol,research,v106,flow,record=record_v11)

    portfolio_state=payload.get('portfolio')
    if portfolio_state is None:
        portfolio_state=flow.get('portfolio') or {}

    out=production_candidate.decision.evaluate(v11,portfolio_state)
    out['source']='BABY_V11_TO_V12'
    out['execution']='NONE'
    return out


@app.post('/api/production/canary/{symbol}')
def production_canary(symbol:str,payload:dict):
    symbol=symbol.upper()

    decision_payload={
        'force':bool(payload.get('force',False)),
        'record_v11':bool(payload.get('record_v11',True)),
    }
    if 'portfolio' in payload:
        decision_payload['portfolio']=payload.get('portfolio')

    decision=production_decision(symbol,decision_payload)
    order=dict(payload.get('order') or {})
    order['symbol']=symbol

    admission=production_candidate.canary.evaluate(
        decision,
        order,
        payload.get('confirmation'),
    )

    result={
        'symbol':symbol,
        'decision':decision,
        'canary_gate':admission,
        'submitted':False,
        'broker_response':None,
    }

    if not bool(payload.get('submit',False)):
        result['status']='DRY_RUN'
        return result

    if not admission.get('eligible'):
        result['status']='BLOCKED'
        return result

    broker_order=admission['order']
    broker_response=alpaca_submit(broker_order)
    result['submitted']=True
    result['broker_response']=broker_response
    result['status']='SUBMITTED'
    production_candidate.ledger.audit(
        'LIVE_CANARY_SUBMITTED',
        (decision.get('proposal') or {}).get('id'),
        {
            'symbol':symbol,
            'notional':broker_order.get('notional'),
            'broker_response':broker_response,
        },
    )
    return result



@app.get('/api/monitor/jobs')
def monitor_jobs():
    return {'status':'READY','jobs':investment_monitor_store.list()}

@app.get('/api/monitor/events')
def monitor_events(symbol: str | None = None, limit: int = 100):
    return {'status':'READY','events':investment_monitor_store.events(symbol,limit)}

@app.post('/api/monitor/jobs/{symbol}')
def monitor_register(symbol: str, payload: dict | None = None):
    payload=payload or {}
    return investment_monitor_store.upsert(
        symbol,
        interval_minutes=int(payload.get('interval_minutes') or 5),
        thesis_review_minutes=int(payload.get('thesis_review_minutes') or 30),
        baseline=payload.get('baseline') or {},
    )

@app.delete('/api/monitor/jobs/{symbol}')
def monitor_disable(symbol: str):
    return investment_monitor_store.disable(symbol) or {'status':'NOT_FOUND'}

@app.post('/api/monitor/jobs/{symbol}/run')
def monitor_run(symbol: str):
    return investment_monitor_worker.run_one(symbol)


@app.get('/api/history/stock/{symbol}')
def stock_history(symbol: str, range_name: str = '1M'):
    return history_service.stock(symbol, range_name)

@app.get('/api/history/portfolio')
def portfolio_history(limit: int = 1000):
    return {'status':'READY','snapshots':investment_monitor_store.snapshots(limit)}

@app.post('/api/monitor/sync')
def monitor_sync():
    return investment_monitor_worker.sync_positions()

@app.get('/api/scheduler/status')
def scheduler_status():
    return baby_operating_scheduler.status()

