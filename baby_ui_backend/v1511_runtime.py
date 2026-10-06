from __future__ import annotations

import os
import threading
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from .v1511_forward_validation import ForwardValidationLedger
from .v1511_mobile_approval import MobileApprovalStore
from .v1511_readiness import ReadinessStore

ET=ZoneInfo('America/New_York')
ledger=ForwardValidationLedger()
approvals=MobileApprovalStore()
readiness=ReadinessStore()
_plain_tokens={}
_lock=threading.Lock()


def _paper(decision):
    payload=((decision or {}).get('proposal') or {}).get('payload') or {}
    return payload.get('paper_proposal') or (decision or {}).get('paper_proposal') or {}


def _episode(symbol):
    import sqlite3
    try:
        db=sqlite3.connect('data/baby_ui.db');db.row_factory=sqlite3.Row
        r=db.execute('SELECT ready_episode,last_ready FROM candidate_alert_state WHERE symbol=?',(symbol.upper(),)).fetchone();db.close()
        if not r:return 1
        cur=int((r['ready_episode'] or 0))
        return max(1,cur if bool(r['last_ready']) else cur+1)
    except Exception:return 1


def observe_candidate(symbol,decision):
    paper=_paper(decision)
    if not paper:return {'status':'NO_PAPER_PROPOSAL'}
    c=readiness.observe(symbol,paper)
    eligible=bool(paper.get('eligible')) and str(paper.get('status') or '').upper()=='ELIGIBLE'
    if eligible:
        ep=_episode(symbol)
        row=ledger.record_ready(symbol,ep,paper,decision)
        token=approvals.create(symbol,ep)
        if token:
            with _lock:_plain_tokens[(symbol.upper(),ep)]=token
        return {'status':'READY_RECORDED','readiness':c,'episode':ep,'validation':row,'approval_created':bool(token)}
    return {'status':'OBSERVED','readiness':c}


def approval_token_for(symbol,episode=None):
    with _lock:
        if episode is not None:return _plain_tokens.get((symbol.upper(),int(episode)))
        matches=[(ep,t) for (s,ep),t in _plain_tokens.items() if s==symbol.upper()]
        return sorted(matches)[-1][1] if matches else None


def market_open_now():
    n=datetime.now(ET)
    if n.weekday()>=5:return False
    mins=n.hour*60+n.minute
    return 570<=mins<=960


class HotWatchWorker:
    def __init__(self,revalidate,quote_getter=None,broker_orders=None,interval=None):
        self.revalidate=revalidate;self.quote_getter=quote_getter;self.broker_orders=broker_orders
        self.interval=max(30,min(int(interval or os.getenv('BABY_HOT_WATCH_SECONDS','60')),300))
        self.stop_event=threading.Event();self.thread=None
    def start(self):
        if self.thread and self.thread.is_alive():return
        self.thread=threading.Thread(target=self._run,name='baby-v1511-hot-watch',daemon=True);self.thread.start()
    def _run(self):
        while not self.stop_event.wait(self.interval):
            try:
                if not market_open_now():continue
                for s in readiness.hot_symbols(limit=int(os.getenv('BABY_HOT_WATCH_MAX','8'))):
                    try:self.revalidate(s)
                    except Exception:pass
                if self.quote_getter:
                    for row in ledger.list(100):
                        if row.get('outcome') not in {'OPEN','UNFILLED','T1_HIT'}:continue
                        try:
                            q=self.quote_getter(row['symbol'])
                            p=q.get('price') if isinstance(q,dict) else getattr(q,'price',None)
                            if p:ledger.observe_price(row['symbol'],p)
                        except Exception:pass
                if self.broker_orders:
                    try:
                        orders=self.broker_orders(100) or []
                        byid={str(o.get('id')):o for o in orders if o.get('id')}
                        for row in ledger.list(200):
                            oid=str(row.get('alpaca_order_id') or '')
                            if not oid or oid not in byid:continue
                            o=byid[oid];st=str(o.get('status') or '').upper()
                            if st in {'FILLED','PARTIALLY_FILLED'}:
                                fp=o.get('filled_avg_price') or o.get('average_fill_price') or row.get('fill_price')
                                ledger.record_fill(row['symbol'],row['ready_episode'],fp,o.get('filled_at'),st)
                    except Exception:pass
            except Exception:pass
