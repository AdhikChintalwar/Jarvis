from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def _now():
    return datetime.now(timezone.utc).isoformat()


def _upper(value):
    return str(value or "").strip().upper()


class MonitoredSetupStore:
    """Durable research/setup watchlist. Stores no account sizing or execution authority."""

    def __init__(self, path="data/baby_monitored_setups.db"):
        self.path=Path(path)
        self.path.parent.mkdir(parents=True,exist_ok=True)
        self._init()

    def _db(self):
        db=sqlite3.connect(self.path,timeout=30)
        db.row_factory=sqlite3.Row
        return db

    def _init(self):
        with self._db() as db:
            db.execute(
                """CREATE TABLE IF NOT EXISTS monitored_setups(
                    symbol TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    state TEXT NOT NULL,
                    ready INTEGER NOT NULL DEFAULT 0,
                    snapshot TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    ready_since TEXT
                )"""
            )
            db.execute("CREATE INDEX IF NOT EXISTS idx_monitored_state ON monitored_setups(state,updated_at)")

    @staticmethod
    def _from_proposal(symbol,proposal,source="ALPACA_PAPER_CHECK"):
        p=proposal or {}
        ready=bool(p.get("eligible")) or _upper(p.get("status"))=="ELIGIBLE"
        state="SETUP_READY" if ready else (_upper(p.get("setup_status")) or _upper(p.get("status")) or "WAITING")
        return {
            "symbol":_upper(symbol),
            "source":source,
            "state":state,
            "ready":ready,
            "quote_price":p.get("quote_price"),
            "quote_quality":p.get("quote_quality"),
            "quote_provider":p.get("quote_provider"),
            "quote_as_of":p.get("quote_as_of"),
            "entry_price":p.get("entry_price"),
            "invalidation":p.get("invalidation"),
            "target_1":p.get("target_1"),
            "target_2":p.get("target_2"),
            "rr_target_1":p.get("rr_target_1"),
            "rr_target_2":p.get("rr_target_2"),
            "risk_level":p.get("risk_level"),
            "reason":p.get("reason"),
            "execution_authority":"NONE",
            "real_money_execution":"DISABLED",
        }

    @classmethod
    def _from_decision(cls,symbol,decision,source="SCHEDULED_REVALIDATION"):
        d=decision or {}
        p=(((d.get("proposal") or {}).get("payload") or {}).get("paper_proposal") or {})
        snap=cls._from_proposal(symbol,p,source)
        snap["production_status"]=d.get("status")
        snap["bridge_failures"]=d.get("bridge_failures") or []
        return snap

    def _upsert(self,snapshot):
        symbol=_upper(snapshot.get("symbol"))
        if not symbol:
            raise ValueError("symbol is required")
        t=_now()
        with self._db() as db:
            old=db.execute("SELECT * FROM monitored_setups WHERE symbol=?",(symbol,)).fetchone()
            old_ready=bool(old["ready"]) if old else False
            new_ready=bool(snapshot.get("ready"))
            created=old["created_at"] if old else t
            ready_since=(old["ready_since"] if old and old_ready and new_ready else (t if new_ready else None))
            db.execute(
                """INSERT INTO monitored_setups(symbol,source,state,ready,snapshot,created_at,updated_at,ready_since)
                   VALUES(?,?,?,?,?,?,?,?)
                   ON CONFLICT(symbol) DO UPDATE SET
                     source=excluded.source,
                     state=excluded.state,
                     ready=excluded.ready,
                     snapshot=excluded.snapshot,
                     updated_at=excluded.updated_at,
                     ready_since=excluded.ready_since""",
                (
                    symbol,
                    str(snapshot.get("source") or "UNKNOWN"),
                    str(snapshot.get("state") or "WAITING"),
                    1 if new_ready else 0,
                    json.dumps(snapshot,default=str),
                    created,
                    t,
                    ready_since,
                ),
            )
        return {
            "symbol":symbol,
            "previous_ready":old_ready,
            "ready":new_ready,
            "transition_to_ready":bool(new_ready and not old_ready),
            "state":snapshot.get("state"),
            "updated_at":t,
        }

    def monitor_proposal(self,symbol,proposal,source="ALPACA_PAPER_CHECK"):
        return self._upsert(self._from_proposal(symbol,proposal,source))

    def update_from_decision(self,symbol,decision,source="SCHEDULED_REVALIDATION"):
        if not self.is_monitored(symbol):
            return {"symbol":_upper(symbol),"monitored":False,"transition_to_ready":False}
        result=self._upsert(self._from_decision(symbol,decision,source))
        result["monitored"]=True
        return result

    def is_monitored(self,symbol):
        with self._db() as db:
            return db.execute("SELECT 1 FROM monitored_setups WHERE symbol=? LIMIT 1",(_upper(symbol),)).fetchone() is not None

    def symbols(self):
        with self._db() as db:
            return [r["symbol"] for r in db.execute("SELECT symbol FROM monitored_setups ORDER BY updated_at DESC").fetchall()]

    def list(self):
        with self._db() as db:
            rows=db.execute("SELECT * FROM monitored_setups ORDER BY ready DESC, updated_at DESC").fetchall()
        out=[]
        for r in rows:
            snap=json.loads(r["snapshot"] or "{}")
            snap.update({
                "created_at":r["created_at"],
                "updated_at":r["updated_at"],
                "ready_since":r["ready_since"],
                "monitored":True,
            })
            out.append(snap)
        return out

    def remove(self,symbol):
        symbol=_upper(symbol)
        with self._db() as db:
            cur=db.execute("DELETE FROM monitored_setups WHERE symbol=?",(symbol,))
        return {"status":"REMOVED" if cur.rowcount else "NOT_FOUND","symbol":symbol}
