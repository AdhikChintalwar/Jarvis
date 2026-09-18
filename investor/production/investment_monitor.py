from __future__ import annotations
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Callable
import json, sqlite3, threading

DB_PATH = Path("data/baby_investment_monitor.db")

def now():
    return datetime.now(timezone.utc)

def iso(dt=None):
    return (dt or now()).isoformat()

class InvestmentMonitorStore:
    def __init__(self, path=DB_PATH):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.conn() as c:
            c.execute("""CREATE TABLE IF NOT EXISTS monitor_jobs(
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
                baseline_stop REAL,
                baseline_target_1 REAL,
                baseline_target_2 REAL
            )""")
            c.execute("""CREATE TABLE IF NOT EXISTS monitor_events(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                created_at TEXT NOT NULL,
                severity TEXT NOT NULL,
                event_type TEXT NOT NULL,
                summary TEXT NOT NULL,
                payload_json TEXT NOT NULL
            )""")
    def conn(self):
        c=sqlite3.connect(self.path)
        c.row_factory=sqlite3.Row
        return c
    def get(self,symbol):
        with self.conn() as c:
            r=c.execute("SELECT * FROM monitor_jobs WHERE symbol=?",(symbol.upper(),)).fetchone()
            return dict(r) if r else None
    def list(self):
        with self.conn() as c:
            return [dict(r) for r in c.execute("SELECT * FROM monitor_jobs ORDER BY symbol")]
    def upsert(self,symbol,interval_minutes=5,thesis_review_minutes=30,baseline=None):
        symbol=symbol.upper().strip()
        baseline=baseline or {}
        old=self.get(symbol)
        created=old["created_at"] if old else iso()
        nxt=iso()
        with self.conn() as c:
            c.execute("""INSERT INTO monitor_jobs(
                symbol,enabled,interval_minutes,thesis_review_minutes,created_at,updated_at,next_run_at,
                last_run_at,last_status,last_decision,last_setup,last_quote_quality,last_price,
                baseline_thesis_state,baseline_stop,baseline_target_1,baseline_target_2
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(symbol) DO UPDATE SET
                enabled=1,interval_minutes=excluded.interval_minutes,
                thesis_review_minutes=excluded.thesis_review_minutes,
                updated_at=excluded.updated_at,next_run_at=excluded.next_run_at,
                baseline_thesis_state=COALESCE(excluded.baseline_thesis_state,monitor_jobs.baseline_thesis_state),
                baseline_stop=COALESCE(excluded.baseline_stop,monitor_jobs.baseline_stop),
                baseline_target_1=COALESCE(excluded.baseline_target_1,monitor_jobs.baseline_target_1),
                baseline_target_2=COALESCE(excluded.baseline_target_2,monitor_jobs.baseline_target_2)
            """,(symbol,1,max(1,int(interval_minutes)),max(5,int(thesis_review_minutes)),created,iso(),nxt,
                 old["last_run_at"] if old else None, old["last_status"] if old else "PENDING",
                 old["last_decision"] if old else None, old["last_setup"] if old else None,
                 old["last_quote_quality"] if old else None, old["last_price"] if old else None,
                 baseline.get("thesis_state"),baseline.get("stop"),baseline.get("target_1"),baseline.get("target_2")))
        return self.get(symbol)
    def disable(self,symbol):
        with self.conn() as c:
            c.execute("UPDATE monitor_jobs SET enabled=0,updated_at=? WHERE symbol=?",(iso(),symbol.upper()))
        return self.get(symbol)
    def due(self):
        with self.conn() as c:
            return [dict(r) for r in c.execute(
                "SELECT * FROM monitor_jobs WHERE enabled=1 AND next_run_at<=? ORDER BY next_run_at",(iso(),))]
    def events(self,symbol=None,limit=100):
        with self.conn() as c:
            if symbol:
                rows=c.execute("SELECT * FROM monitor_events WHERE symbol=? ORDER BY id DESC LIMIT ?",
                               (symbol.upper(),int(limit))).fetchall()
            else:
                rows=c.execute("SELECT * FROM monitor_events ORDER BY id DESC LIMIT ?",(int(limit),)).fetchall()
        out=[]
        for r in rows:
            d=dict(r)
            try:d["payload"]=json.loads(d.pop("payload_json"))
            except Exception:d["payload"]={}
            out.append(d)
        return out
    def record(self,symbol,result,events):
        job=self.get(symbol)
        if not job:return
        nxt=now()+timedelta(minutes=max(1,int(job["interval_minutes"])))
        with self.conn() as c:
            c.execute("""UPDATE monitor_jobs SET updated_at=?,next_run_at=?,last_run_at=?,last_status=?,
                         last_decision=?,last_setup=?,last_quote_quality=?,last_price=? WHERE symbol=?""",
                      (iso(),iso(nxt),iso(),result.get("monitor_status","OK"),result.get("production_status"),
                       result.get("setup_status"),result.get("quote_quality"),result.get("price"),symbol.upper()))
            for e in events:
                c.execute("""INSERT INTO monitor_events(symbol,created_at,severity,event_type,summary,payload_json)
                             VALUES(?,?,?,?,?,?)""",
                          (symbol.upper(),iso(),e["severity"],e["event_type"],e["summary"],json.dumps(e.get("payload") or {})))

def evaluate_monitor_result(job,decision,quote):
    payload=(decision.get("proposal") or {}).get("payload") or {}
    paper=payload.get("paper_proposal") or {}
    price=quote.get("price")
    setup=payload.get("setup_status")
    pstatus=decision.get("status")
    events=[]
    def add(sev,typ,summary,**payload):
        events.append({"severity":sev,"event_type":typ,"summary":summary,"payload":payload})
    if job.get("last_setup") and setup and job["last_setup"]!=setup:
        add("INFO","SETUP_CHANGED",f"{job['symbol']} setup changed from {job['last_setup']} to {setup}",
            previous=job["last_setup"],current=setup)
    if job.get("last_decision") and pstatus and job["last_decision"]!=pstatus:
        add("REVIEW","PRODUCTION_STATUS_CHANGED",
            f"{job['symbol']} production status changed from {job['last_decision']} to {pstatus}",
            previous=job["last_decision"],current=pstatus)
    try:
        stop=job.get("baseline_stop")
        if price is not None and stop is not None and float(price)<=float(stop):
            add("URGENT","INVALIDATION_REACHED",f"{job['symbol']} reached/passed stored invalidation.",price=price,stop=stop)
        t1=job.get("baseline_target_1")
        if price is not None and t1 is not None and float(price)>=float(t1):
            add("REVIEW","TARGET_1_REACHED",f"{job['symbol']} reached/passed stored target 1.",price=price,target=t1)
        t2=job.get("baseline_target_2")
        if price is not None and t2 is not None and float(price)>=float(t2):
            add("REVIEW","TARGET_2_REACHED",f"{job['symbol']} reached/passed stored target 2.",price=price,target=t2)
    except Exception:
        pass
    if paper.get("trade_quality_status")=="BLOCKED":
        add("REVIEW","TRADE_QUALITY_DEGRADED",f"{job['symbol']} no longer passes trade-quality policy.",
            failures=paper.get("gate_failures") or [])
    if quote.get("execution_eligible") is False:
        add("INFO","QUOTE_NOT_EXECUTION_GRADE",f"{job['symbol']} quote is not execution-grade.",
            issues=quote.get("validation_issues") or [])
    status="REVIEW" if any(e["severity"] in {"URGENT","REVIEW"} for e in events) else "OK"
    return {
        "symbol":job["symbol"],"monitor_status":status,"production_status":pstatus,
        "setup_status":setup,"quote_quality":quote.get("quality"),"price":price,"checked_at":iso()
    },events

class InvestmentMonitorWorker:
    def __init__(self,store,evaluator,quote_getter,sleep_seconds=20):
        self.store=store;self.evaluator=evaluator;self.quote_getter=quote_getter
        self.sleep_seconds=max(5,int(sleep_seconds));self.stop_event=threading.Event();self.thread=None
    def start(self):
        if self.thread and self.thread.is_alive():return
        self.thread=threading.Thread(target=self.loop,name="baby-investment-monitor",daemon=True);self.thread.start()
    def run_one(self,symbol):
        job=self.store.get(symbol)
        if not job:raise ValueError("monitor job not found")
        decision=self.evaluator(symbol);quote=self.quote_getter(symbol)
        result,events=evaluate_monitor_result(job,decision,quote);self.store.record(symbol,result,events)
        return {"result":result,"events":events}
    def loop(self):
        while not self.stop_event.is_set():
            for job in self.store.due():
                try:self.run_one(job["symbol"])
                except Exception as e:
                    self.store.record(job["symbol"],{"monitor_status":"ERROR"},[
                        {"severity":"REVIEW","event_type":"MONITOR_ERROR","summary":str(e),"payload":{}}])
            self.stop_event.wait(self.sleep_seconds)
