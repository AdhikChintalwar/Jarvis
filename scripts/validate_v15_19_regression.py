import sqlite3
import tempfile
from pathlib import Path
from types import SimpleNamespace

from fastapi import HTTPException

from baby_ui_backend.v1519_strategy_analytics import (
    StrategyAnalytics,
    runtime as analytics_runtime,
)

from baby_ui_backend import v1516_quick


def pass_(msg):
    print("PASS:", msg)


# ============================================================
# 1. ANALYTICS / REALIZED P&L / REALIZED R
# ============================================================

with tempfile.TemporaryDirectory() as td:
    path = Path(td) / "analytics.db"

    db = sqlite3.connect(path)

    db.executescript("""
    CREATE TABLE v1511_forward_validation(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT,
        ready_episode INTEGER,
        t0 TEXT,
        filled INTEGER,
        first_fill_at TEXT,
        fill_price REAL,
        quantity REAL,
        invalidation REAL,
        target1 REAL,
        target2 REAL,
        paper_outcome TEXT,
        paper_mfe_pct REAL,
        paper_mae_pct REAL,
        paper_closed_at TEXT
    );

    CREATE TABLE v1517_entry_confirmation(
        symbol TEXT,
        ready_episode INTEGER,
        strategy_version TEXT,
        state TEXT,
        entry_quality_score REAL,
        diagnostics_json TEXT,
        updated_at TEXT
    );

    CREATE TABLE v1518_exit_state(
        symbol TEXT,
        ready_episode INTEGER,
        strategy_version TEXT,
        original_quantity REAL,
        remaining_quantity REAL,
        initial_stop REAL,
        protected_stop REAL,
        highest_r REAL,
        t1_filled_qty REAL,
        t1_fill_price REAL,
        final_filled_qty REAL,
        final_fill_price REAL,
        final_reason TEXT,
        state TEXT,
        updated_at TEXT
    );
    """)

    db.execute("""
        INSERT INTO v1511_forward_validation(
            symbol,ready_episode,t0,filled,first_fill_at,
            fill_price,quantity,invalidation,target1,target2,
            paper_outcome,paper_mfe_pct,paper_mae_pct
        )
        VALUES(
            'AAA',1,
            '2026-11-05T00:00:00+00:00',
            1,
            '2026-11-05T00:01:00+00:00',
            100,10,99,102,103,
            'T2_HIT',3.5,-0.4
        )
    """)

    db.execute("""
        INSERT INTO v1517_entry_confirmation(
            symbol,ready_episode,strategy_version,state,
            entry_quality_score,diagnostics_json,updated_at
        )
        VALUES(
            'AAA',1,'ENTRY_V2','CONFIRMED',
            88,'{"trend":"bullish"}',
            '2026-11-05T00:00:30+00:00'
        )
    """)

    db.execute("""
        INSERT INTO v1518_exit_state(
            symbol,ready_episode,strategy_version,
            original_quantity,remaining_quantity,
            initial_stop,protected_stop,highest_r,
            t1_filled_qty,t1_fill_price,
            final_filled_qty,final_fill_price,
            final_reason,state,updated_at
        )
        VALUES(
            'AAA',1,'EXIT_V2',
            10,0,
            99,100.1,3,
            5,102,
            5,103,
            'T2_TARGET','CLOSED',
            '2026-11-05T01:00:00+00:00'
        )
    """)

    db.commit()
    db.close()

    service = StrategyAnalytics(path)

    trades = service.trades(3650)

    assert len(trades) == 1

    t = trades[0]

    assert t["strategy_version"] == "ENTRY_V2+EXIT_V2"
    assert t["realized_pnl"] == 25.0
    assert t["realized_r"] == 2.5
    assert t["entry_quality_score"] == 88
    assert t["final_reason"] == "T2_TARGET"

    summary = service.overview(3650)
    perf = summary["by_strategy_version"]["ENTRY_V2+EXIT_V2"]

    assert perf["trades"] == 1
    assert perf["resolved"] == 1
    assert perf["wins"] == 1
    assert perf["win_rate_pct"] == 100.0
    assert perf["expectancy_r"] == 2.5
    assert perf["total_realized_pnl"] == 25.0

pass_("realized PAPER P&L and R are calculated correctly")


# ============================================================
# 2. RECONCILIATION CLASSIFICATION
# ============================================================

with tempfile.TemporaryDirectory() as td:
    path = Path(td) / "reconcile.db"

    db = sqlite3.connect(path)

    db.executescript("""
    CREATE TABLE v1511_forward_validation(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT,
        ready_episode INTEGER,
        quantity REAL,
        paper_outcome TEXT,
        fill_price REAL,
        filled INTEGER
    );
    """)

    # Clean match
    db.execute("""
        INSERT INTO v1511_forward_validation
        VALUES(NULL,'MATCH',1,10,'OPEN',100,1)
    """)

    # Ledger open / broker zero
    db.execute("""
        INSERT INTO v1511_forward_validation
        VALUES(NULL,'ZERO',1,7,'OPEN',50,1)
    """)

    # Multiple live episodes
    db.execute("""
        INSERT INTO v1511_forward_validation
        VALUES(NULL,'MULTI',1,5,'OPEN',20,1)
    """)

    db.execute("""
        INSERT INTO v1511_forward_validation
        VALUES(NULL,'MULTI',2,5,'OPEN',20,1)
    """)

    # Analytical close but broker still owns shares
    db.execute("""
        INSERT INTO v1511_forward_validation
        VALUES(NULL,'ORPHAN',1,4,'T2_HIT',30,1)
    """)

    db.commit()
    db.close()

    analytics_runtime.position_getter = lambda: [
        {"symbol":"MATCH","qty":10},
        {"symbol":"MULTI","qty":10},
        {"symbol":"ORPHAN","qty":4},
    ]

    service = StrategyAnalytics(path)
    recon = service.reconciliation()

    status = {
        r["symbol"]: r["status"]
        for r in recon["positions"]
    }

    assert status["MATCH"] == "MATCH"
    assert status["ZERO"] == "LEDGER_OPEN_BROKER_ZERO"
    assert status["MULTI"] == "MULTIPLE_LIVE_EPISODES"
    assert status["ORPHAN"] == "BROKER_POSITION_LEDGER_CLOSED"

pass_("broker/ledger reconciliation classifications are correct")


# ============================================================
# 3. BROKER FAILURE MUST FAIL CLOSED
# ============================================================

with tempfile.TemporaryDirectory() as td:
    path = Path(td) / "brokerfail.db"

    db = sqlite3.connect(path)

    db.executescript("""
    CREATE TABLE v1511_forward_validation(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT,
        ready_episode INTEGER,
        quantity REAL,
        paper_outcome TEXT,
        fill_price REAL,
        filled INTEGER
    );

    INSERT INTO v1511_forward_validation
    VALUES(NULL,'AAA',1,10,'OPEN',100,1);
    """)

    db.commit()
    db.close()

    def broken_positions():
        raise RuntimeError("broker unavailable")

    analytics_runtime.position_getter = broken_positions

    recon = StrategyAnalytics(path).reconciliation()

    assert recon["broker_error"] is not None

    assert all(
        x["status"] == "BROKER_UNKNOWN"
        for x in recon["positions"]
    )

pass_("analytics reconciliation fails closed on broker failure")


# ============================================================
# 4. QUICK BROKER POSITION HELPER
# ============================================================

original_store = v1516_quick.store
original_runtime = v1516_quick.runtime

try:
    v1516_quick.runtime.position_getter = lambda: [
        {"symbol":"ABC","qty":12}
    ]

    assert v1516_quick._broker_position_qty("ABC") == 12
    assert v1516_quick._broker_position_qty("XYZ") == 0

    v1516_quick.runtime.position_getter = lambda: (
        (_ for _ in ()).throw(
            RuntimeError("broker down")
        )
    )

    assert v1516_quick._broker_position_qty("ABC") is None

finally:
    pass

pass_("Quick broker helper distinguishes held/zero/unknown")


# ============================================================
# 5. QUICK BUY MUST BLOCK DUPLICATE SYMBOL
# ============================================================

class FakeStore:
    def __init__(self, path):
        self.path = path

    def db(self):
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        return db

    def audit(self, *args, **kwargs):
        pass


with tempfile.TemporaryDirectory() as td:
    path = Path(td) / "quick.db"

    db = sqlite3.connect(path)

    db.executescript("""
    CREATE TABLE v1511_forward_validation(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT,
        ready_episode INTEGER,
        t0 TEXT,
        entry REAL,
        invalidation REAL,
        target1 REAL,
        target2 REAL,
        quote_price REAL,
        paper_outcome TEXT,
        alpaca_order_id TEXT,
        filled INTEGER,
        quantity REAL
    );

    CREATE TABLE v1511_readiness(
        symbol TEXT PRIMARY KEY,
        state TEXT
    );

    CREATE TABLE candidate_alert_state(
        symbol TEXT PRIMARY KEY,
        ready_episode INTEGER,
        last_ready INTEGER
    );

    CREATE TABLE v1515_daily_guard(
        trade_date TEXT PRIMARY KEY,
        new_entries INTEGER NOT NULL DEFAULT 0,
        start_equity REAL
    );

    INSERT INTO v1511_forward_validation(
        symbol,ready_episode,t0,entry,invalidation,
        target1,target2,quote_price,paper_outcome,
        alpaca_order_id,filled,quantity
    )
    VALUES(
        'ABC',1,'2026-11-05T00:00:00+00:00',
        100,99,102,103,100,'NOT_EXECUTED',
        NULL,0,NULL
    );

    INSERT INTO v1511_readiness
    VALUES('ABC','SETUP_READY');

    INSERT INTO candidate_alert_state
    VALUES('ABC',1,1);
    """)

    db.commit()
    db.close()

    old_store = v1516_quick.store
    old_runtime = v1516_quick.runtime

    try:
        v1516_quick.store = FakeStore(path)

        fake_runtime = SimpleNamespace(
            position_getter=lambda:[
                {"symbol":"ABC","qty":5}
            ],
            proposal_getter=lambda s:{
                "eligible":True,
                "status":"ELIGIBLE",
                "invalidation":99,
            },
            quote_getter=lambda s:{
                "price":100
            },
            account_getter=lambda:{
                "equity":100000
            },
            order_submitter=lambda **kwargs: (
                (_ for _ in ()).throw(
                    AssertionError(
                        "BUY should never submit"
                    )
                )
            ),
            ledger=object(),
        )

        v1516_quick.runtime = fake_runtime

        try:
            v1516_quick.approve_existing("ABC",1)
            raise AssertionError(
                "duplicate symbol BUY was not blocked"
            )
        except HTTPException as exc:
            assert exc.status_code == 409
            assert "position already exists" in str(
                exc.detail
            ).lower()

    finally:
        v1516_quick.store = old_store
        v1516_quick.runtime = old_runtime

pass_("Quick duplicate-symbol BUY is blocked")


# ============================================================
# 6. QUICK BUY BROKER UNKNOWN MUST FAIL CLOSED
# ============================================================

with tempfile.TemporaryDirectory() as td:
    path = Path(td) / "quick_unknown.db"

    db = sqlite3.connect(path)

    db.executescript("""
    CREATE TABLE v1511_forward_validation(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT,
        ready_episode INTEGER,
        t0 TEXT,
        entry REAL,
        invalidation REAL,
        target1 REAL,
        target2 REAL,
        quote_price REAL,
        paper_outcome TEXT,
        alpaca_order_id TEXT,
        filled INTEGER,
        quantity REAL
    );

    CREATE TABLE v1511_readiness(
        symbol TEXT PRIMARY KEY,
        state TEXT
    );

    CREATE TABLE candidate_alert_state(
        symbol TEXT PRIMARY KEY,
        ready_episode INTEGER,
        last_ready INTEGER
    );

    CREATE TABLE v1515_daily_guard(
        trade_date TEXT PRIMARY KEY,
        new_entries INTEGER NOT NULL DEFAULT 0,
        start_equity REAL
    );

    INSERT INTO v1511_forward_validation
    VALUES(
        NULL,'ABC',1,
        '2026-11-05T00:00:00+00:00',
        100,99,102,103,100,
        'NOT_EXECUTED',
        NULL,0,NULL
    );

    INSERT INTO v1511_readiness
    VALUES('ABC','SETUP_READY');

    INSERT INTO candidate_alert_state
    VALUES('ABC',1,1);
    """)

    db.commit()
    db.close()

    old_store = v1516_quick.store
    old_runtime = v1516_quick.runtime

    try:
        v1516_quick.store = FakeStore(path)

        v1516_quick.runtime = SimpleNamespace(
            position_getter=lambda: (
                (_ for _ in ()).throw(
                    RuntimeError("broker down")
                )
            ),
            proposal_getter=lambda s:{},
            quote_getter=lambda s:{},
            account_getter=lambda:{},
            order_submitter=lambda **kwargs:None,
            ledger=object(),
        )

        try:
            v1516_quick.approve_existing("ABC",1)
            raise AssertionError(
                "unknown broker state was not blocked"
            )
        except HTTPException as exc:
            assert exc.status_code == 503

    finally:
        v1516_quick.store = old_store
        v1516_quick.runtime = old_runtime

pass_("Quick BUY fails closed when broker state is unknown")


# ============================================================
# 7. QUICK CLOSE MUST USE BROKER-SAFE QUANTITY
# ============================================================

with tempfile.TemporaryDirectory() as td:
    path = Path(td) / "quick_close.db"

    db = sqlite3.connect(path)

    db.executescript("""
    CREATE TABLE v1511_forward_validation(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT,
        ready_episode INTEGER,
        filled INTEGER,
        quantity REAL,
        paper_outcome TEXT
    );

    INSERT INTO v1511_forward_validation
    VALUES(NULL,'ABC',1,1,10,'T1_HIT');
    """)

    db.commit()
    db.close()

    submitted=[]

    old_store = v1516_quick.store
    old_runtime = v1516_quick.runtime

    try:
        v1516_quick.store = FakeStore(path)

        v1516_quick.runtime = SimpleNamespace(
            position_getter=lambda:[
                {"symbol":"ABC","qty":4}
            ],
            order_submitter=lambda **kwargs: (
                submitted.append(kwargs)
                or {
                    "id":"sell-1",
                    "status":"ACCEPTED",
                }
            ),
        )

        result = v1516_quick.close_existing(
            "ABC",
            1,
        )

        assert len(submitted) == 1
        assert submitted[0]["side"] == "SELL"
        assert submitted[0]["quantity"] == 4
        assert result["quantity"] == 4
        assert result["broker_quantity"] == 4

    finally:
        v1516_quick.store = old_store
        v1516_quick.runtime = old_runtime

pass_("Quick close uses broker quantity after partial exit")


# ============================================================
# 8. QUICK CLOSE MULTIPLE EPISODES MUST BLOCK
# ============================================================

with tempfile.TemporaryDirectory() as td:
    path = Path(td) / "quick_multi.db"

    db = sqlite3.connect(path)

    db.executescript("""
    CREATE TABLE v1511_forward_validation(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT,
        ready_episode INTEGER,
        filled INTEGER,
        quantity REAL,
        paper_outcome TEXT
    );

    INSERT INTO v1511_forward_validation
    VALUES(NULL,'ABC',1,1,5,'OPEN');

    INSERT INTO v1511_forward_validation
    VALUES(NULL,'ABC',2,1,5,'OPEN');
    """)

    db.commit()
    db.close()

    old_store = v1516_quick.store
    old_runtime = v1516_quick.runtime

    try:
        v1516_quick.store = FakeStore(path)

        v1516_quick.runtime = SimpleNamespace(
            position_getter=lambda:[
                {"symbol":"ABC","qty":10}
            ],
            order_submitter=lambda **kwargs: (
                (_ for _ in ()).throw(
                    AssertionError(
                        "SELL must not submit"
                    )
                )
            ),
        )

        try:
            v1516_quick.close_existing(
                "ABC",
                1,
            )

            raise AssertionError(
                "multi-episode close not blocked"
            )

        except HTTPException as exc:
            assert exc.status_code == 409
            assert "multiple live" in str(
                exc.detail
            ).lower()

    finally:
        v1516_quick.store = old_store
        v1516_quick.runtime = old_runtime

pass_("Quick close blocks ambiguous multi-episode symbol")


print()
print("========================================")
print("V15.19 STRONG REGRESSION SUITE PASS")
print("========================================")
