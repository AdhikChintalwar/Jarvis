from __future__ import annotations

from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Callable
import json
import sqlite3
import threading

DB_PATH = Path("data/baby_investment_monitor.db")

def utcnow():
    return datetime.now(timezone.utc)

def iso(dt=None):
    return (dt or utcnow()).isoformat()

def as_float(v):
    try:
        return float(v)
    except Exception:
        return None

class InvestmentMonitorStore:
    def __init__(self, path=DB_PATH):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _conn(self):
        c = sqlite3.connect(self.path)
        c.row_factory = sqlite3.Row
        return c

    def _columns(self, c, table):
        return {r["name"] for r in c.execute(f"PRAGMA table_info({table})")}

    def _add_column(self, c, table, spec):
        name = spec.split()[0]
        if name not in self._columns(c, table):
            c.execute(f"ALTER TABLE {table} ADD COLUMN {spec}")

    def _init(self):
        with self._conn() as c:
            c.execute("""
            CREATE TABLE IF NOT EXISTS monitor_jobs(
              symbol TEXT PRIMARY KEY,
              enabled INTEGER NOT NULL DEFAULT 1,
              interval_minutes INTEGER NOT NULL DEFAULT 5,
              thesis_review_minutes INTEGER NOT NULL DEFAULT 30,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              next_run_at TEXT NOT NULL,
              last_run_at TEXT,
              last_status TEXT NOT NULL DEFAULT 'PENDING',
              last_decision TEXT,
              last_setup TEXT,
              last_quote_quality TEXT,
              last_price REAL,
              baseline_thesis_state TEXT,
              baseline_entry REAL,
              baseline_stop REAL,
              baseline_target_1 REAL,
              baseline_target_2 REAL,
              source TEXT DEFAULT 'MANUAL'
            )""")
            c.execute("""
            CREATE TABLE IF NOT EXISTS monitor_events(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              symbol TEXT NOT NULL,
              created_at TEXT NOT NULL,
              severity TEXT NOT NULL,
              event_type TEXT NOT NULL,
              summary TEXT NOT NULL,
              payload_json TEXT NOT NULL
            )""")
            c.execute("""
            CREATE TABLE IF NOT EXISTS portfolio_snapshots(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              created_at TEXT NOT NULL,
              equity REAL,
              cash REAL,
              buying_power REAL,
              position_count INTEGER NOT NULL DEFAULT 0,
              environment TEXT
            )""")
            for spec in [
                "last_fast_check_at TEXT",
                "last_thesis_review_at TEXT",
                "next_thesis_review_at TEXT",
                "closed_at TEXT",
                "baseline_entry REAL",
                "source TEXT DEFAULT 'MANUAL'",
            ]:
                self._add_column(c, "monitor_jobs", spec)
            c.commit()

    def get(self, symbol):
        with self._conn() as c:
            r = c.execute("SELECT * FROM monitor_jobs WHERE symbol=?", (symbol.upper(),)).fetchone()
            return dict(r) if r else None

    def list(self):
        with self._conn() as c:
            return [dict(r) for r in c.execute("SELECT * FROM monitor_jobs ORDER BY enabled DESC,symbol")]

    def events(self, symbol=None, limit=100):
        with self._conn() as c:
            if symbol:
                rows = c.execute(
                    "SELECT * FROM monitor_events WHERE symbol=? ORDER BY id DESC LIMIT ?",
                    (symbol.upper(), int(limit))
                ).fetchall()
            else:
                rows = c.execute(
                    "SELECT * FROM monitor_events ORDER BY id DESC LIMIT ?", (int(limit),)
                ).fetchall()
        out=[]
        for r in rows:
            d=dict(r)
            try:
                d["payload"]=json.loads(d.pop("payload_json"))
            except Exception:
                d["payload"]={}
            out.append(d)
        return out

    def emit(self, symbol, severity, event_type, summary, payload=None):
        with self._conn() as c:
            c.execute(
                """INSERT INTO monitor_events(symbol,created_at,severity,event_type,summary,payload_json)
                   VALUES(?,?,?,?,?,?)""",
                (symbol.upper(), iso(), severity, event_type, summary, json.dumps(payload or {}))
            )
            c.commit()

    def upsert(self, symbol, interval_minutes=5, thesis_review_minutes=30,
               baseline=None, source="MANUAL"):
        symbol = symbol.upper().strip()
        if not symbol:
            raise ValueError("symbol required")
        baseline = baseline or {}
        now = utcnow()
        old = self.get(symbol)
        created = old["created_at"] if old else iso(now)
        next_deep = iso(now + timedelta(minutes=max(5,int(thesis_review_minutes))))
        with self._conn() as c:
            c.execute("""
            INSERT INTO monitor_jobs(
              symbol,enabled,interval_minutes,thesis_review_minutes,created_at,updated_at,next_run_at,
              last_run_at,last_status,last_decision,last_setup,last_quote_quality,last_price,
              baseline_thesis_state,baseline_entry,baseline_stop,baseline_target_1,baseline_target_2,
              source,last_fast_check_at,last_thesis_review_at,next_thesis_review_at,closed_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(symbol) DO UPDATE SET
              enabled=1,
              interval_minutes=excluded.interval_minutes,
              thesis_review_minutes=excluded.thesis_review_minutes,
              updated_at=excluded.updated_at,
              next_run_at=excluded.next_run_at,
              next_thesis_review_at=COALESCE(monitor_jobs.next_thesis_review_at,excluded.next_thesis_review_at),
              baseline_thesis_state=COALESCE(excluded.baseline_thesis_state,monitor_jobs.baseline_thesis_state),
              baseline_entry=COALESCE(excluded.baseline_entry,monitor_jobs.baseline_entry),
              baseline_stop=COALESCE(excluded.baseline_stop,monitor_jobs.baseline_stop),
              baseline_target_1=COALESCE(excluded.baseline_target_1,monitor_jobs.baseline_target_1),
              baseline_target_2=COALESCE(excluded.baseline_target_2,monitor_jobs.baseline_target_2),
              source=excluded.source,
              closed_at=NULL
            """,(
                symbol,1,max(1,int(interval_minutes)),max(5,int(thesis_review_minutes)),
                created,iso(now),iso(now),
                old.get("last_run_at") if old else None,
                old.get("last_status","PENDING") if old else "PENDING",
                old.get("last_decision") if old else None,
                old.get("last_setup") if old else None,
                old.get("last_quote_quality") if old else None,
                old.get("last_price") if old else None,
                baseline.get("thesis_state"),
                baseline.get("entry"),
                baseline.get("stop"),
                baseline.get("target_1"),
                baseline.get("target_2"),
                source,
                old.get("last_fast_check_at") if old else None,
                old.get("last_thesis_review_at") if old else None,
                old.get("next_thesis_review_at") if old else next_deep,
                None,
            ))
            c.commit()
        return self.get(symbol)

    def disable(self, symbol, reason="POSITION_CLOSED"):
        symbol=symbol.upper()
        with self._conn() as c:
            c.execute("""UPDATE monitor_jobs SET enabled=0,updated_at=?,closed_at=? WHERE symbol=?""",
                      (iso(),iso(),symbol))
            c.commit()
        self.emit(symbol,"INFO","MONITOR_DISABLED",f"{symbol} monitor disabled: {reason}",{"reason":reason})
        return self.get(symbol)

    def due_fast(self):
        with self._conn() as c:
            return [dict(r) for r in c.execute(
                "SELECT * FROM monitor_jobs WHERE enabled=1 AND next_run_at<=? ORDER BY next_run_at",(iso(),)
            )]

    def deep_due(self, job):
        v=job.get("next_thesis_review_at")
        if not v:
            return True
        try:
            return datetime.fromisoformat(v.replace("Z","+00:00")) <= utcnow()
        except Exception:
            return True

    def record_fast(self, job, quote, events):
        now=utcnow()
        next_fast=now+timedelta(minutes=max(1,int(job["interval_minutes"])))
        price=as_float(quote.get("price"))
        with self._conn() as c:
            c.execute("""UPDATE monitor_jobs SET updated_at=?,next_run_at=?,last_run_at=?,
                         last_fast_check_at=?,last_price=?,last_quote_quality=?,last_status=?
                         WHERE symbol=?""",
                      (iso(now),iso(next_fast),iso(now),iso(now),price,
                       quote.get("quality"),"REVIEW" if any(e["severity"] in {"REVIEW","URGENT"} for e in events) else "OK",
                       job["symbol"]))
            c.commit()
        for e in events:
            self.emit(job["symbol"],e["severity"],e["event_type"],e["summary"],e.get("payload"))

    def record_deep(self, job, decision, events):
        now=utcnow()
        next_deep=now+timedelta(minutes=max(5,int(job["thesis_review_minutes"])))
        payload=(decision.get("proposal") or {}).get("payload") or {}
        with self._conn() as c:
            c.execute("""UPDATE monitor_jobs SET updated_at=?,last_thesis_review_at=?,next_thesis_review_at=?,
                         last_decision=?,last_setup=?,last_status=? WHERE symbol=?""",
                      (iso(now),iso(now),iso(next_deep),decision.get("status"),
                       payload.get("setup_status"),
                       "REVIEW" if any(e["severity"] in {"REVIEW","URGENT"} for e in events) else "OK",
                       job["symbol"]))
            c.commit()
        for e in events:
            self.emit(job["symbol"],e["severity"],e["event_type"],e["summary"],e.get("payload"))

    def add_snapshot(self, account, positions):
        with self._conn() as c:
            c.execute("""INSERT INTO portfolio_snapshots(created_at,equity,cash,buying_power,position_count,environment)
                         VALUES(?,?,?,?,?,?)""",
                      (iso(),as_float(account.get("equity")),as_float(account.get("cash")),
                       as_float(account.get("buying_power")),len(positions or []),account.get("environment")))
            c.commit()

    def snapshots(self, limit=1000):
        with self._conn() as c:
            rows=c.execute("SELECT * FROM portfolio_snapshots ORDER BY id DESC LIMIT ?",(int(limit),)).fetchall()
        return [dict(r) for r in reversed(rows)]

def fast_events(job, quote):
    events=[]
    symbol=job["symbol"]
    price=as_float(quote.get("price"))
    old=as_float(job.get("last_price"))
    stop=as_float(job.get("baseline_stop"))
    t1=as_float(job.get("baseline_target_1"))
    t2=as_float(job.get("baseline_target_2"))

    def add(sev,typ,summary,**payload):
        events.append({"severity":sev,"event_type":typ,"summary":summary,"payload":payload})

    if quote.get("execution_eligible") is False:
        add("INFO","QUOTE_NOT_EXECUTION_GRADE",f"{symbol} quote is not execution-grade.",
            issues=quote.get("validation_issues") or [])
    if price is not None and stop is not None and price <= stop:
        add("URGENT","INVALIDATION_REACHED",f"{symbol} reached/passed its stored invalidation level.",
            price=price,stop=stop)
    if price is not None and t1 is not None and price >= t1 and (old is None or old < t1):
        add("REVIEW","TARGET_1_REACHED",f"{symbol} reached stored target 1.",price=price,target_1=t1)
    if price is not None and t2 is not None and price >= t2 and (old is None or old < t2):
        add("REVIEW","TARGET_2_REACHED",f"{symbol} reached stored target 2.",price=price,target_2=t2)
    return events

def deep_events(job, decision):
    events=[]
    symbol=job["symbol"]
    payload=(decision.get("proposal") or {}).get("payload") or {}
    paper=payload.get("paper_proposal") or {}
    setup=payload.get("setup_status")
    old_setup=job.get("last_setup")
    old_decision=job.get("last_decision")
    new_decision=decision.get("status")

    def add(sev,typ,summary,**payload):
        events.append({"severity":sev,"event_type":typ,"summary":summary,"payload":payload})

    if old_setup and setup and old_setup != setup:
        add("REVIEW","SETUP_CHANGED",f"{symbol} setup changed: {old_setup} -> {setup}",
            previous=old_setup,current=setup)
    if old_decision and new_decision and old_decision != new_decision:
        add("REVIEW","PRODUCTION_STATUS_CHANGED",
            f"{symbol} production status changed: {old_decision} -> {new_decision}",
            previous=old_decision,current=new_decision)
    if paper.get("trade_quality_status")=="BLOCKED":
        add("REVIEW","TRADE_QUALITY_DEGRADED",
            f"{symbol} does not currently satisfy the deterministic trade-quality gate.",
            failures=paper.get("gate_failures") or [])
    thesis=payload.get("thesis_state")
    baseline=job.get("baseline_thesis_state")
    if baseline and thesis and thesis != baseline:
        add("REVIEW","THESIS_STATE_CHANGED",f"{symbol} thesis state changed: {baseline} -> {thesis}",
            baseline=baseline,current=thesis)
    return events

class InvestmentMonitorWorker:
    def __init__(self, store, quote_getter, deep_evaluator=None, positions_getter=None,
                 account_getter=None, sync_seconds=60, loop_seconds=15):
        self.store=store
        self.quote_getter=quote_getter
        self.deep_evaluator=deep_evaluator
        self.positions_getter=positions_getter
        self.account_getter=account_getter
        self.sync_seconds=max(30,int(sync_seconds))
        self.loop_seconds=max(5,int(loop_seconds))
        self._stop=threading.Event()
        self._thread=None
        self._last_sync=None

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._thread=threading.Thread(target=self._run,name="baby-position-monitor",daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()

    def sync_positions(self):
        if not self.positions_getter:
            return {"status":"NO_POSITION_PROVIDER","created":[],"disabled":[]}
        raw=self.positions_getter()
        positions=raw.get("positions",raw) if isinstance(raw,dict) else raw
        positions=positions or []
        held={}
        for p in positions:
            s=str(p.get("symbol") or "").upper().strip()
            qty=as_float(p.get("qty",p.get("quantity")))
            if s and (qty is None or qty != 0):
                held[s]=p

        existing={j["symbol"]:j for j in self.store.list()}
        created=[]
        for symbol,p in held.items():
            if symbol not in existing or not existing[symbol].get("enabled"):
                baseline={
                    "entry":as_float(p.get("avg_entry_price",p.get("average_entry_price"))),
                }
                self.store.upsert(symbol,5,30,baseline,source="ALPACA_POSITION_SYNC")
                self.store.emit(symbol,"INFO","MONITOR_AUTO_CREATED",
                                f"{symbol} monitor created from broker position.",
                                {"position":p})
                created.append(symbol)

        disabled=[]
        for symbol,j in existing.items():
            if j.get("enabled") and j.get("source")=="ALPACA_POSITION_SYNC" and symbol not in held:
                self.store.disable(symbol,"POSITION_NO_LONGER_PRESENT")
                disabled.append(symbol)

        if self.account_getter:
            try:
                account=self.account_getter() or {}
                self.store.add_snapshot(account,positions)
            except Exception:
                pass
        self._last_sync=iso()
        return {"status":"READY","created":created,"disabled":disabled,
                "held_symbols":sorted(held),"synced_at":self._last_sync}

    def run_fast(self, symbol):
        job=self.store.get(symbol)
        if not job:
            raise ValueError("monitor job not found")
        quote=self.quote_getter(symbol)
        events=fast_events(job,quote)
        self.store.record_fast(job,quote,events)
        return {"symbol":symbol,"kind":"FAST","quote":quote,"events":events}

    def run_deep(self, symbol):
        if not self.deep_evaluator:
            return {"symbol":symbol,"kind":"DEEP","status":"NO_DEEP_EVALUATOR","events":[]}
        job=self.store.get(symbol)
        decision=self.deep_evaluator(symbol)
        events=deep_events(job,decision)
        self.store.record_deep(job,decision,events)
        return {"symbol":symbol,"kind":"DEEP","decision":decision,"events":events}

    def run_one(self, symbol, include_deep=True):
        out={"fast":self.run_fast(symbol)}
        job=self.store.get(symbol)
        if include_deep and self.deep_evaluator and self.store.deep_due(job):
            out["deep"]=self.run_deep(symbol)
        return out

    def _run(self):
        next_sync=utcnow()
        while not self._stop.is_set():
            now=utcnow()
            if self.positions_getter and now>=next_sync:
                try:self.sync_positions()
                except Exception as e:
                    self.store.emit("SYSTEM","REVIEW","POSITION_SYNC_ERROR",str(e),{})
                next_sync=now+timedelta(seconds=self.sync_seconds)

            for job in self.store.due_fast():
                try:
                    self.run_fast(job["symbol"])
                    refreshed=self.store.get(job["symbol"])
                    if self.deep_evaluator and self.store.deep_due(refreshed):
                        self.run_deep(job["symbol"])
                except Exception as e:
                    self.store.emit(job["symbol"],"REVIEW","MONITOR_ERROR",str(e),{})
            self._stop.wait(self.loop_seconds)
