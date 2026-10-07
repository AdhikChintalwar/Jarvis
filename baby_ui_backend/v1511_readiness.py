from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def _u(v): return str(v or "").upper().strip()

def _now(): return datetime.now(timezone.utc).isoformat()


ACTIVE = {"AT_PULLBACK_ZONE", "BREAKOUT_TRIGGERED", "ACTIVE", "ENTRY_ZONE"}


def classify(paper: dict) -> dict:
    eligible = bool(paper.get("eligible")) and _u(paper.get("status")) == "ELIGIBLE"
    setup = _u(paper.get("setup_status") or paper.get("status"))
    tq = _u(paper.get("trade_quality_status"))
    eq = _u(paper.get("execution_quote_status"))
    failures = [_u(x) for x in (paper.get("gate_failures") or [])]
    active = setup in ACTIVE
    quote_only = bool(failures) and all(x == "EXECUTION_QUOTE_NOT_ELIGIBLE" for x in failures)
    if eligible:
        state, score, reason = "SETUP_READY", 100, "All final deterministic PAPER gates pass."
    elif active and tq == "PASS" and (quote_only or eq == "BLOCKED"):
        state, score, reason = "NEAR_READY", 92, "Active setup and trade quality pass; execution quote is the remaining blocker."
    elif active and tq == "PASS":
        state, score, reason = "NEAR_READY", 86, "Active setup and trade quality pass; one or more final gates remain."
    elif active:
        state, score, reason = "ACTIVE_SETUP", 72, "Deterministic setup is active but final quality/risk gates are not all satisfied."
    elif setup in {"WAIT_FOR_PULLBACK_OR_BREAKOUT", "WAITING", "SETUP_FORMING"}:
        state, score, reason = "SETUP_FORMING", 58, "Research candidate has a plan but entry conditions are not active."
    else:
        state, score, reason = "MONITOR", 40, "Research interest only; no active deterministic PAPER setup."
    return {"state": state, "readiness_potential": score, "reason": reason, "setup_status": setup, "failures": failures}


class ReadinessStore:
    def __init__(self, path="data/baby_ui.db"):
        self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True); self._init()
    def _db(self):
        db=sqlite3.connect(self.path,timeout=30); db.row_factory=sqlite3.Row; return db
    def _init(self):
        with self._db() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS v1511_readiness(
              symbol TEXT PRIMARY KEY,state TEXT NOT NULL,readiness_potential INTEGER NOT NULL,reason TEXT,
              setup_status TEXT,failures_json TEXT,updated_at TEXT NOT NULL)""")
            db.execute("""CREATE TABLE IF NOT EXISTS v1512_readiness_history(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              symbol TEXT NOT NULL,
              state TEXT NOT NULL,
              readiness_potential INTEGER,
              reason TEXT,
              setup_status TEXT,
              failures_json TEXT,
              observed_at TEXT NOT NULL
            )""")
            db.execute("""CREATE INDEX IF NOT EXISTS idx_v1512_hist_time
              ON v1512_readiness_history(observed_at)""")
            db.commit()
    def observe(self,symbol,paper):
        import json
        c=classify(paper)
        with self._db() as db:
            observed_at = _now()
            failures_json = json.dumps(c['failures'])

            db.execute("""INSERT INTO v1511_readiness(symbol,state,readiness_potential,reason,setup_status,failures_json,updated_at)
              VALUES(?,?,?,?,?,?,?) ON CONFLICT(symbol) DO UPDATE SET state=excluded.state,readiness_potential=excluded.readiness_potential,
              reason=excluded.reason,setup_status=excluded.setup_status,failures_json=excluded.failures_json,updated_at=excluded.updated_at""",
              (symbol.upper(),c['state'],c['readiness_potential'],c['reason'],c['setup_status'],failures_json,observed_at))

            db.execute("""INSERT INTO v1512_readiness_history(
              symbol,state,readiness_potential,reason,setup_status,failures_json,observed_at
            ) VALUES(?,?,?,?,?,?,?)""",
              (symbol.upper(),c['state'],c['readiness_potential'],c['reason'],c['setup_status'],failures_json,observed_at))

            db.commit()
        return c
    def list(self,limit=100):
        with self._db() as db:
            rows=db.execute("SELECT * FROM v1511_readiness ORDER BY readiness_potential DESC, updated_at DESC LIMIT ?",(max(1,min(int(limit),500)),)).fetchall()
        return [dict(r) for r in rows]
    def hot_symbols(self,limit=8):
        with self._db() as db:
            rows=db.execute("SELECT symbol FROM v1511_readiness WHERE state IN ('NEAR_READY','SETUP_READY') ORDER BY readiness_potential DESC,updated_at DESC LIMIT ?",(max(1,min(int(limit),20)),)).fetchall()
        return [r['symbol'] for r in rows]
