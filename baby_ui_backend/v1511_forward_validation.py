from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _f(v):
    try:
        return float(v)
    except Exception:
        return None


def _u(v):
    return str(v or "").upper().strip()


def _pct_move(value, ref):
    if value is None or ref in (None, 0):
        return None
    return ((value / ref) - 1.0) * 100.0


class ForwardValidationLedger:
    """
    Forward-only SETUP_READY ledger.

    Two separate tracks are maintained:

    1. theoretical_*:
       Grades Baby's frozen T0 plan independently of whether the user approved
       an Alpaca PAPER trade. Entry must be established before a target/stop
       can count.

    2. paper_*:
       Grades the actual Alpaca PAPER execution only after a broker fill.
       Pre-fill price movement never contaminates PAPER MFE/MAE or outcomes.
    """

    def __init__(self, path: str = "data/baby_ui.db"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _db(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        return db

    @staticmethod
    def _ensure_columns(db):
        cols = {r[1] for r in db.execute("PRAGMA table_info(v1511_forward_validation)").fetchall()}
        wanted = {
            "theoretical_entry_at": "TEXT",
            "theoretical_outcome": "TEXT NOT NULL DEFAULT 'UNFILLED'",
            "theoretical_mfe_pct": "REAL",
            "theoretical_mae_pct": "REAL",
            "theoretical_max_price": "REAL",
            "theoretical_min_price": "REAL",
            "theoretical_t1_hit_at": "TEXT",
            "theoretical_t2_hit_at": "TEXT",
            "theoretical_stop_hit_at": "TEXT",
            "theoretical_closed_at": "TEXT",
            "paper_outcome": "TEXT NOT NULL DEFAULT 'NOT_EXECUTED'",
            "paper_mfe_pct": "REAL",
            "paper_mae_pct": "REAL",
            "paper_max_price": "REAL",
            "paper_min_price": "REAL",
            "paper_t1_hit_at": "TEXT",
            "paper_t2_hit_at": "TEXT",
            "paper_stop_hit_at": "TEXT",
            "paper_closed_at": "TEXT",
        }
        for name, sql_type in wanted.items():
            if name not in cols:
                db.execute(f"ALTER TABLE v1511_forward_validation ADD COLUMN {name} {sql_type}")

    def _init(self):
        with self._db() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS v1511_forward_validation(
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  symbol TEXT NOT NULL,
                  ready_episode INTEGER NOT NULL,
                  setup_type TEXT,
                  setup_status TEXT,
                  t0 TEXT NOT NULL,
                  entry REAL,
                  invalidation REAL,
                  target1 REAL,
                  target2 REAL,
                  rr1 REAL,
                  rr2 REAL,
                  quote_price REAL,
                  quote_provider TEXT,
                  quote_asof TEXT,
                  outcome TEXT NOT NULL DEFAULT 'UNFILLED',
                  filled INTEGER NOT NULL DEFAULT 0,
                  first_fill_at TEXT,
                  fill_price REAL,
                  alpaca_order_id TEXT,
                  order_status TEXT,
                  quantity REAL,
                  mfe_pct REAL,
                  mae_pct REAL,
                  max_price REAL,
                  min_price REAL,
                  t1_hit_at TEXT,
                  t2_hit_at TEXT,
                  stop_hit_at TEXT,
                  closed_at TEXT,
                  last_observed_at TEXT,
                  source_json TEXT,
                  theoretical_entry_at TEXT,
                  theoretical_outcome TEXT NOT NULL DEFAULT 'UNFILLED',
                  theoretical_mfe_pct REAL,
                  theoretical_mae_pct REAL,
                  theoretical_max_price REAL,
                  theoretical_min_price REAL,
                  theoretical_t1_hit_at TEXT,
                  theoretical_t2_hit_at TEXT,
                  theoretical_stop_hit_at TEXT,
                  theoretical_closed_at TEXT,
                  paper_outcome TEXT NOT NULL DEFAULT 'NOT_EXECUTED',
                  paper_mfe_pct REAL,
                  paper_mae_pct REAL,
                  paper_max_price REAL,
                  paper_min_price REAL,
                  paper_t1_hit_at TEXT,
                  paper_t2_hit_at TEXT,
                  paper_stop_hit_at TEXT,
                  paper_closed_at TEXT,
                  UNIQUE(symbol, ready_episode)
                );
                CREATE TABLE IF NOT EXISTS v1511_forward_events(
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  validation_id INTEGER,
                  symbol TEXT NOT NULL,
                  event_type TEXT NOT NULL,
                  observed_at TEXT NOT NULL,
                  price REAL,
                  payload_json TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_v1511_validation_symbol ON v1511_forward_validation(symbol);
                CREATE INDEX IF NOT EXISTS idx_v1511_validation_outcome ON v1511_forward_validation(outcome);
                """
            )
            self._ensure_columns(db)
            db.commit()

    @staticmethod
    def _t0_entry_state(paper, t0):
        entry = _f(paper.get("entry_price"))
        quote = _f(paper.get("quote_price"))
        if entry is None or quote is None or entry <= 0:
            return None, "UNFILLED"
        # SETUP_READY is an active current setup. When the frozen current quote
        # is already essentially at the frozen entry, treat the theoretical
        # plan as filled at T0. This uses only information known at T0.
        if abs(quote - entry) / entry <= 0.0025:
            return t0, "OPEN"
        return None, "UNFILLED"

    def record_ready(self, symbol: str, episode: int, paper: dict[str, Any], source: dict[str, Any] | None = None):
        symbol = symbol.upper().strip()
        episode = max(1, int(episode or 1))
        t0 = _now()
        theoretical_entry_at, theoretical_outcome = self._t0_entry_state(paper, t0)
        values = (
            symbol,
            episode,
            str(paper.get("setup_type") or ""),
            str(paper.get("setup_status") or paper.get("status") or ""),
            t0,
            _f(paper.get("entry_price")),
            _f(paper.get("invalidation")),
            _f(paper.get("target_1")),
            _f(paper.get("target_2")),
            _f(paper.get("rr_target_1")),
            _f(paper.get("rr_target_2")),
            _f(paper.get("quote_price")),
            str(paper.get("quote_provider") or paper.get("provider") or ""),
            str(paper.get("quote_asof") or paper.get("asof") or ""),
            theoretical_outcome,
            theoretical_entry_at,
            theoretical_outcome,
            json.dumps(source or {}, default=str, separators=(",", ":")),
        )
        with self._db() as db:
            db.execute(
                """
                INSERT OR IGNORE INTO v1511_forward_validation(
                  symbol,ready_episode,setup_type,setup_status,t0,entry,invalidation,target1,target2,rr1,rr2,
                  quote_price,quote_provider,quote_asof,outcome,theoretical_entry_at,theoretical_outcome,source_json
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                values,
            )
            row = db.execute(
                "SELECT * FROM v1511_forward_validation WHERE symbol=? AND ready_episode=?",
                (symbol, episode),
            ).fetchone()
            db.commit()
        return dict(row) if row else None

    def attach_order(self, symbol: str, episode: int, order: dict[str, Any], quantity: float):
        oid = str(order.get("id") or order.get("order_id") or "")
        status = str(order.get("status") or "SUBMITTED").upper()
        with self._db() as db:
            db.execute(
                """UPDATE v1511_forward_validation
                   SET alpaca_order_id=?, order_status=?, quantity=?,
                       paper_outcome=CASE WHEN filled=1 THEN paper_outcome ELSE 'UNFILLED' END,
                       last_observed_at=?
                   WHERE symbol=? AND ready_episode=?""",
                (oid, status, quantity, _now(), symbol.upper(), int(episode)),
            )
            row = db.execute(
                "SELECT * FROM v1511_forward_validation WHERE symbol=? AND ready_episode=?",
                (symbol.upper(), int(episode)),
            ).fetchone()
            db.commit()
        return dict(row) if row else None

    def record_fill(self, symbol: str, episode: int, fill_price: float | None, filled_at: str | None = None, order_status: str = "FILLED"):
        at = filled_at or _now()
        fp = _f(fill_price)
        with self._db() as db:
            db.execute(
                """UPDATE v1511_forward_validation
                   SET filled=1,
                       first_fill_at=COALESCE(first_fill_at,?),
                       fill_price=COALESCE(fill_price,?),
                       order_status=?,
                       paper_outcome=CASE WHEN paper_outcome IN ('NOT_EXECUTED','UNFILLED') THEN 'OPEN' ELSE paper_outcome END,
                       paper_max_price=COALESCE(paper_max_price,?),
                       paper_min_price=COALESCE(paper_min_price,?),
                       last_observed_at=?
                   WHERE symbol=? AND ready_episode=?""",
                (at, fp, order_status, fp, fp, _now(), symbol.upper(), int(episode)),
            )
            db.commit()

    @staticmethod
    def _entry_touched(d, p):
        entry = _f(d.get("entry"))
        if entry is None:
            return False
        setup_type = _u(d.get("setup_type"))
        if "BREAKOUT" in setup_type:
            return p >= entry
        return p <= entry

    @staticmethod
    def _grade_track(d, p, observed_at, prefix, ref):
        """
        Grade one already-entered long track. Returns dict of updates.
        """
        max_key = f"{prefix}_max_price"
        min_key = f"{prefix}_min_price"
        outcome_key = f"{prefix}_outcome"
        t1_key = f"{prefix}_t1_hit_at"
        t2_key = f"{prefix}_t2_hit_at"
        stop_key = f"{prefix}_stop_hit_at"
        closed_key = f"{prefix}_closed_at"

        old_max = _f(d.get(max_key))
        old_min = _f(d.get(min_key))
        maxp = max(x for x in (old_max, p) if x is not None)
        minp = min(x for x in (old_min, p) if x is not None)
        mfe = _pct_move(maxp, ref)
        mae = _pct_move(minp, ref)

        outcome = d.get(outcome_key) or "OPEN"
        t1_at = d.get(t1_key)
        t2_at = d.get(t2_key)
        stop_at = d.get(stop_key)

        # A single point observation cannot establish intrabar ordering if
        # multiple levels were crossed between observations. We therefore
        # record only the state directly implied by the current observation.
        stop = _f(d.get("invalidation"))
        t1 = _f(d.get("target1"))
        t2 = _f(d.get("target2"))

        if stop_at is None and stop is not None and p <= stop:
            stop_at = observed_at
            outcome = "T1_THEN_STOP" if t1_at else "STOPPED"
        elif t2_at is None and t2 is not None and p >= t2:
            if t1_at is None:
                t1_at = observed_at
            t2_at = observed_at
            outcome = "T2_HIT"
        elif t1_at is None and t1 is not None and p >= t1:
            t1_at = observed_at
            outcome = "T1_HIT"

        closed = observed_at if outcome in {"STOPPED", "T1_THEN_STOP", "T2_HIT"} else d.get(closed_key)
        return {
            max_key: maxp,
            min_key: minp,
            f"{prefix}_mfe_pct": mfe,
            f"{prefix}_mae_pct": mae,
            t1_key: t1_at,
            t2_key: t2_at,
            stop_key: stop_at,
            outcome_key: outcome,
            closed_key: closed,
        }

    def observe_price(self, symbol: str, price: float, observed_at: str | None = None):
        p = _f(price)
        if p is None or p <= 0:
            return []
        observed_at = observed_at or _now()
        updates = []
        with self._db() as db:
            rows = db.execute(
                """SELECT * FROM v1511_forward_validation
                   WHERE symbol=?
                     AND (
                       theoretical_outcome IN ('UNFILLED','OPEN','T1_HIT')
                       OR paper_outcome IN ('UNFILLED','OPEN','T1_HIT')
                     )
                   ORDER BY id""",
                (symbol.upper(),),
            ).fetchall()

            for row in rows:
                d = dict(row)

                # ---- Theoretical T0 plan track --------------------------------
                if (d.get("theoretical_outcome") or "UNFILLED") == "UNFILLED" and self._entry_touched(d, p):
                    d["theoretical_entry_at"] = observed_at
                    d["theoretical_outcome"] = "OPEN"
                    db.execute(
                        """UPDATE v1511_forward_validation
                           SET theoretical_entry_at=?, theoretical_outcome='OPEN',
                               theoretical_max_price=?, theoretical_min_price=?,
                               outcome='OPEN', max_price=?, min_price=?, last_observed_at=?
                           WHERE id=?""",
                        (observed_at, p, p, p, p, observed_at, d["id"]),
                    )
                    d["theoretical_max_price"] = p
                    d["theoretical_min_price"] = p

                theoretical = None
                if d.get("theoretical_outcome") in {"OPEN", "T1_HIT"}:
                    tref = _f(d.get("entry"))
                    theoretical = self._grade_track(d, p, observed_at, "theoretical", tref)
                    db.execute(
                        """UPDATE v1511_forward_validation SET
                           theoretical_max_price=?, theoretical_min_price=?,
                           theoretical_mfe_pct=?, theoretical_mae_pct=?,
                           theoretical_t1_hit_at=?, theoretical_t2_hit_at=?, theoretical_stop_hit_at=?,
                           theoretical_outcome=?, theoretical_closed_at=?,
                           outcome=?, max_price=?, min_price=?, mfe_pct=?, mae_pct=?,
                           t1_hit_at=?, t2_hit_at=?, stop_hit_at=?, closed_at=?,
                           last_observed_at=?
                           WHERE id=?""",
                        (
                            theoretical["theoretical_max_price"], theoretical["theoretical_min_price"],
                            theoretical["theoretical_mfe_pct"], theoretical["theoretical_mae_pct"],
                            theoretical["theoretical_t1_hit_at"], theoretical["theoretical_t2_hit_at"], theoretical["theoretical_stop_hit_at"],
                            theoretical["theoretical_outcome"], theoretical["theoretical_closed_at"],
                            theoretical["theoretical_outcome"],
                            theoretical["theoretical_max_price"], theoretical["theoretical_min_price"],
                            theoretical["theoretical_mfe_pct"], theoretical["theoretical_mae_pct"],
                            theoretical["theoretical_t1_hit_at"], theoretical["theoretical_t2_hit_at"], theoretical["theoretical_stop_hit_at"],
                            theoretical["theoretical_closed_at"], observed_at, d["id"],
                        ),
                    )

                # ---- Actual Alpaca PAPER fill track ---------------------------
                paper = None
                if bool(d.get("filled")) and d.get("paper_outcome") in {"OPEN", "T1_HIT"}:
                    pref = _f(d.get("fill_price"))
                    if pref:
                        paper = self._grade_track(d, p, observed_at, "paper", pref)
                        db.execute(
                            """UPDATE v1511_forward_validation SET
                               paper_max_price=?, paper_min_price=?,
                               paper_mfe_pct=?, paper_mae_pct=?,
                               paper_t1_hit_at=?, paper_t2_hit_at=?, paper_stop_hit_at=?,
                               paper_outcome=?, paper_closed_at=?, last_observed_at=?
                               WHERE id=?""",
                            (
                                paper["paper_max_price"], paper["paper_min_price"],
                                paper["paper_mfe_pct"], paper["paper_mae_pct"],
                                paper["paper_t1_hit_at"], paper["paper_t2_hit_at"], paper["paper_stop_hit_at"],
                                paper["paper_outcome"], paper["paper_closed_at"], observed_at, d["id"],
                            ),
                        )

                db.execute(
                    "INSERT INTO v1511_forward_events(validation_id,symbol,event_type,observed_at,price,payload_json) VALUES(?,?,?,?,?,?)",
                    (
                        d["id"],
                        symbol.upper(),
                        "PRICE_OBSERVATION",
                        observed_at,
                        p,
                        json.dumps(
                            {
                                "theoretical_outcome": (theoretical or {}).get("theoretical_outcome", d.get("theoretical_outcome")),
                                "paper_outcome": (paper or {}).get("paper_outcome", d.get("paper_outcome")),
                            },
                            separators=(",", ":"),
                        ),
                    ),
                )
                updates.append(
                    {
                        "id": d["id"],
                        "symbol": symbol.upper(),
                        "theoretical_outcome": (theoretical or {}).get("theoretical_outcome", d.get("theoretical_outcome")),
                        "paper_outcome": (paper or {}).get("paper_outcome", d.get("paper_outcome")),
                    }
                )
            db.commit()
        return updates

    def list(self, limit: int = 200):
        with self._db() as db:
            rows = db.execute(
                "SELECT * FROM v1511_forward_validation ORDER BY id DESC LIMIT ?",
                (max(1, min(int(limit), 1000)),),
            ).fetchall()
        return [dict(r) for r in rows]

    def summary(self):
        rows = self.list(1000)
        theoretical = {}
        paper = {}
        for r in rows:
            to = r.get("theoretical_outcome") or r.get("outcome") or "UNFILLED"
            po = r.get("paper_outcome") or ("OPEN" if r.get("filled") else "NOT_EXECUTED")
            theoretical[to] = theoretical.get(to, 0) + 1
            paper[po] = paper.get(po, 0) + 1
        return {
            "total": len(rows),
            "theoretical_outcomes": theoretical,
            "paper_outcomes": paper,
            "real_money_execution": "DISABLED",
        }
