
from __future__ import annotations

import json, os, sqlite3, threading, time, urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

PAPER_CONFIRMATION = "EXECUTE ALPACA PAPER"

def _now():
    return datetime.now(timezone.utc).isoformat()

def _f(v):
    try:
        return float(v)
    except Exception:
        return None

class NtfyPush:
    def __init__(self):
        self.enabled = os.getenv("BABY_NTFY_ENABLED","false").lower()=="true"
        self.topic = (os.getenv("BABY_NTFY_TOPIC") or "").strip()
        self.base = (os.getenv("BABY_NTFY_BASE_URL") or "https://ntfy.sh").rstrip("/")

    def send(self, title, message, priority="high", tags="chart_with_upwards_trend"):
        if not (self.enabled and self.topic):
            return {"sent":False,"reason":"NTFY_DISABLED_OR_UNCONFIGURED"}
        req=urllib.request.Request(
            f"{self.base}/{self.topic}",
            data=message.encode(),
            method="POST",
            headers={"Title":title,"Priority":priority,"Tags":tags}
        )
        with urllib.request.urlopen(req, timeout=8) as r:
            return {"sent":200 <= r.status < 300,"status":r.status}

class PaperAutopilotWorker:
    """
    Autonomous Alpaca PAPER entry/exit worker.

    Safety:
      - PAPER broker callback only
      - max 20% allocation per entry
      - risk-to-stop can reduce size
      - max 3 new entries/day
      - no chase when proposal no longer ELIGIBLE
      - only sells positions tracked in v1511_forward_validation
      - real money has no route here
    """
    def __init__(
        self, db_path, proposal_getter, quote_getter, account_getter,
        order_submitter, ledger, notifier=None, interval_seconds=5
    ):
        self.db_path=Path(db_path)
        self.proposal_getter=proposal_getter
        self.quote_getter=quote_getter
        self.account_getter=account_getter
        self.order_submitter=order_submitter
        self.ledger=ledger
        self.notifier=notifier
        self.push=NtfyPush()
        self.interval=max(2,int(interval_seconds))
        self.stop_event=threading.Event()
        self.thread=None
        self.max_alloc=float(os.getenv("BABY_PAPER_MAX_ALLOCATION_PCT","0.20"))
        self.max_trades=int(os.getenv("BABY_PAPER_MAX_NEW_TRADES_PER_DAY","3"))
        self.max_risk=float(os.getenv("BABY_PAPER_MAX_PORTFOLIO_RISK_PCT","0.01"))
        self.enabled=os.getenv("BABY_PAPER_AUTOPILOT_ENABLED","true").lower()=="true"

    def _db(self):
        db=sqlite3.connect(self.db_path)
        db.row_factory=sqlite3.Row
        return db

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        self.thread=threading.Thread(target=self._loop,daemon=True,name="baby-v1515-autopilot")
        self.thread.start()

    def stop(self):
        self.stop_event.set()

    def _log(self,symbol,episode,action,reason,payload=None):
        try:
            with self._db() as db:
                db.execute("""INSERT INTO v1515_actions(symbol,episode_key,action,reason,payload_json,created_at)
                              VALUES(?,?,?,?,?,?)""",
                           (symbol,str(episode),action,reason,json.dumps(payload or {},default=str),_now()))
                db.commit()
        except Exception:
            pass

    def _notify(self,title,message,symbol=None):
        try:self.push.send(title,message)
        except Exception:pass
        try:
            if self.notifier:
                self.notifier.emit(
                    dedupe_key=f"v1515:{title}:{symbol}:{hash(message)}",
                    title=title,message=message,severity="IMPORTANT",
                    symbol=symbol,force=True
                )
        except Exception:pass

    @staticmethod
    def _equity(account):
        if not isinstance(account,dict): return None
        for k in ("equity","portfolio_value","account_equity"):
            v=_f(account.get(k))
            if v and v>0:return v
        return None

    @staticmethod
    def _price(q):
        if not isinstance(q,dict): return None
        for k in ("price","last","last_price","mid","quote_price"):
            v=_f(q.get(k))
            if v and v>0:return v
        bid=_f(q.get("bid_price") or q.get("bid"))
        ask=_f(q.get("ask_price") or q.get("ask"))
        if bid and ask:return (bid+ask)/2
        return ask or bid

    def _trades_today(self):
        today=datetime.now(timezone.utc).date().isoformat()
        with self._db() as db:
            row=db.execute("SELECT new_entries FROM v1515_daily_guard WHERE trade_date=?",(today,)).fetchone()
            return int(row["new_entries"]) if row else 0

    def _increment_today(self,equity):
        today=datetime.now(timezone.utc).date().isoformat()
        with self._db() as db:
            db.execute("""INSERT INTO v1515_daily_guard(trade_date,new_entries,starting_equity,last_updated_at)
                          VALUES(?,1,?,?)
                          ON CONFLICT(trade_date) DO UPDATE SET
                            new_entries=new_entries+1,last_updated_at=excluded.last_updated_at""",
                       (today,equity,_now()))
            db.commit()

    def _candidate_rows(self):
        # V15.15 hotfix: historical validation rows are evidence only.
        max_age_seconds=max(
            30,
            int(os.getenv("BABY_PAPER_ENTRY_MAX_AGE_SECONDS","180"))
        )
        cutoff=(datetime.now(timezone.utc)-timedelta(seconds=max_age_seconds)).isoformat()

        with self._db() as db:
            rows=db.execute("""
              SELECT fv.*
              FROM v1511_forward_validation fv
              JOIN v1511_readiness r
                ON r.symbol=fv.symbol
               AND r.state='SETUP_READY'
              JOIN candidate_alert_state c
                ON c.symbol=fv.symbol
               AND c.last_ready=1
               AND c.ready_episode=fv.ready_episode
              WHERE fv.alpaca_order_id IS NULL
                AND fv.paper_outcome IN ('NOT_EXECUTED','UNFILLED')
                AND fv.t0 >= ?
                AND fv.id=(
                    SELECT MAX(x.id)
                    FROM v1511_forward_validation x
                    WHERE x.symbol=fv.symbol
                )
              ORDER BY fv.t0 ASC
              LIMIT 25
            """,(cutoff,)).fetchall()
            return [dict(r) for r in rows]

    def _open_paper_rows(self):
        with self._db() as db:
            rows=db.execute("""
              SELECT * FROM v1511_forward_validation
              WHERE filled=1
                AND quantity IS NOT NULL
                AND quantity>0
                AND paper_outcome='OPEN'
              ORDER BY id ASC
            """).fetchall()
            return [dict(r) for r in rows]

    def _already_actioned(self,symbol,episode,action):
        with self._db() as db:
            r=db.execute("""SELECT 1 FROM v1515_actions
                            WHERE symbol=? AND episode_key=? AND action=? LIMIT 1""",
                         (symbol,str(episode),action)).fetchone()
            return bool(r)

    def _size(self,equity,price,stop):
        qty_alloc=int((equity*self.max_alloc)//price)
        if qty_alloc<=0:return 0
        qty=qty_alloc
        if stop and stop>0 and stop<price:
            per_share=price-stop
            qty_risk=int((equity*self.max_risk)//per_share) if per_share>0 else qty_alloc
            qty=min(qty,qty_risk)
        return max(0,qty)

    def _enter_once(self,row):
        symbol=row["symbol"]; episode=int(row["ready_episode"])
        if self._already_actioned(symbol,episode,"ENTRY_SUBMITTED"):
            return
        if self._trades_today()>=self.max_trades:
            self._log(symbol,episode,"ENTRY_BLOCKED","DAILY_TRADE_LIMIT_REACHED")
            return

        proposal=self.proposal_getter(symbol)
        if not (proposal.get("eligible") and str(proposal.get("status") or "").upper()=="ELIGIBLE"):
            if not self._already_actioned(symbol,episode,"ENTRY_BLOCKED_NOT_ELIGIBLE"):
                self._log(symbol,episode,"ENTRY_BLOCKED_NOT_ELIGIBLE","SETUP_NO_LONGER_ELIGIBLE",proposal)
            return

        quote=self.quote_getter(symbol)
        px=self._price(quote)
        if not px:
            self._log(symbol,episode,"ENTRY_BLOCKED","NO_FRESH_QUOTE",quote)
            return

        account=self.account_getter()
        equity=self._equity(account)
        if not equity:
            self._log(symbol,episode,"ENTRY_BLOCKED","NO_ACCOUNT_EQUITY",account)
            return

        stop=_f(
            proposal.get("invalidation")
            or proposal.get("stop")
            or proposal.get("stop_price")
            or row.get("invalidation")
        )
        qty=self._size(equity,px,stop)
        if qty<=0:
            self._log(symbol,episode,"ENTRY_BLOCKED","POSITION_SIZE_ZERO",
                      {"equity":equity,"price":px,"stop":stop})
            return

        # Atomic local claim before broker call.
        self._log(symbol,episode,"ENTRY_CLAIMED","AUTOPILOT",
                  {"qty":qty,"price":px,"equity":equity})
        try:
            order=self.order_submitter(
                symbol=symbol, side="BUY", quantity=qty,
                order_type="MARKET", confirmation=PAPER_CONFIRMATION,
                client_order_id=f"baby-v1515-{symbol.lower()}-{episode}"
            )
        except Exception as exc:
            self._log(symbol,episode,"ENTRY_SUBMIT_UNKNOWN","BROKER_EXCEPTION",{"error":str(exc)})
            return

        oid=order.get("id") or order.get("order_id")
        if not oid:
            self._log(symbol,episode,"ENTRY_SUBMIT_UNKNOWN","BROKER_NO_ORDER_ID",order)
            return

        self.ledger.attach_order(symbol,episode,order,qty)
        self._increment_today(equity)
        self._log(symbol,episode,"ENTRY_SUBMITTED","ALPACA_PAPER",order)
        self._notify(
            f"BABY — {symbol} PAPER entry submitted",
            f"{qty} shares submitted to Alpaca PAPER. Episode {episode}. "
            f"Approx quote ${px:.2f}. Real-money execution DISABLED.",
            symbol
        )

    def _exit_if_needed(self,row):
        symbol=row["symbol"]; episode=int(row["ready_episode"])
        if self._already_actioned(symbol,episode,"EXIT_SUBMITTED"):
            return
        q=self.quote_getter(symbol)
        px=self._price(q)
        if not px:return

        stop=_f(row.get("invalidation"))
        fill=_f(row.get("fill_price") or row.get("entry"))
        qty=_f(row.get("quantity"))
        if not qty or qty<=0:return

        reason=None
        if stop and px<=stop:
            reason="STOP_OR_INVALIDATION"
        elif fill and px<=fill*0.95:
            reason="EMERGENCY_5PCT_DROP_FROM_FILL"

        if not reason:return

        self._log(symbol,episode,"EXIT_CLAIMED",reason,{"price":px,"qty":qty})
        try:
            order=self.order_submitter(
                symbol=symbol, side="SELL", quantity=qty,
                order_type="MARKET", confirmation=PAPER_CONFIRMATION,
                client_order_id=f"baby-v1515-exit-{symbol.lower()}-{episode}"
            )
        except Exception as exc:
            self._log(symbol,episode,"EXIT_SUBMIT_UNKNOWN","BROKER_EXCEPTION",{"error":str(exc)})
            return

        oid=order.get("id") or order.get("order_id")
        if not oid:
            self._log(symbol,episode,"EXIT_SUBMIT_UNKNOWN","BROKER_NO_ORDER_ID",order)
            return

        self._log(symbol,episode,"EXIT_SUBMITTED",reason,order)
        self._notify(
            f"BABY — {symbol} PAPER exit submitted",
            f"SELL {qty:g} shares submitted to Alpaca PAPER. Reason: {reason}. "
            f"Quote ${px:.2f}. Real-money execution DISABLED.",
            symbol
        )

    def _loop(self):
        while not self.stop_event.is_set():
            try:
                if self.enabled:
                    for row in self._candidate_rows():
                        self._enter_once(row)
                    for row in self._open_paper_rows():
                        self._exit_if_needed(row)
            except Exception as exc:
                self._log(None,0,"WORKER_ERROR","LOOP_EXCEPTION",{"error":str(exc)})
            self.stop_event.wait(self.interval)
