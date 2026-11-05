import sqlite3
import tempfile
from pathlib import Path

from baby_ui_backend.v1519_strategy_analytics import (
    StrategyAnalytics,
    runtime,
)


with tempfile.TemporaryDirectory() as td:
    path=Path(td)/"baby.db"

    db=sqlite3.connect(path)

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
            symbol,
            ready_episode,
            t0,
            filled,
            first_fill_at,
            fill_price,
            quantity,
            invalidation,
            target1,
            target2,
            paper_outcome,
            paper_mfe_pct,
            paper_mae_pct
        )
        VALUES(
            'TEST',
            1,
            '2026-11-05T00:00:00+00:00',
            1,
            '2026-11-05T00:01:00+00:00',
            100,
            10,
            99,
            102,
            103,
            'T2_HIT',
            3.5,
            -0.4
        )
    """)

    db.execute("""
        INSERT INTO v1517_entry_confirmation(
            symbol,
            ready_episode,
            strategy_version,
            state,
            entry_quality_score,
            diagnostics_json,
            updated_at
        )
        VALUES(
            'TEST',
            1,
            'ENTRY_V2',
            'CONFIRMED',
            88,
            '{"trend":"bullish"}',
            '2026-11-05T00:00:30+00:00'
        )
    """)

    db.execute("""
        INSERT INTO v1518_exit_state(
            symbol,
            ready_episode,
            strategy_version,
            original_quantity,
            remaining_quantity,
            initial_stop,
            protected_stop,
            highest_r,
            t1_filled_qty,
            t1_fill_price,
            final_filled_qty,
            final_fill_price,
            final_reason,
            state,
            updated_at
        )
        VALUES(
            'TEST',
            1,
            'EXIT_V2',
            10,
            0,
            99,
            100.1,
            3.0,
            5,
            102,
            5,
            103,
            'T2_TARGET',
            'CLOSED',
            '2026-11-05T01:00:00+00:00'
        )
    """)

    db.commit()
    db.close()

    s=StrategyAnalytics(path)

    rows=s.trades(3650)

    assert len(rows)==1

    r=rows[0]

    assert (
        r["strategy_version"]
        == "ENTRY_V2+EXIT_V2"
    )

    # 5 shares +$2, 5 shares +$3 = $25
    assert r["realized_pnl"]==25.0

    # Original risk = 10 * ($100-$99) = $10
    assert r["realized_r"]==2.5

    assert r["entry_quality_score"]==88
    assert r["final_reason"]=="T2_TARGET"

    summary=s.overview(3650)

    v=summary[
        "by_strategy_version"
    ]["ENTRY_V2+EXIT_V2"]

    assert v["resolved"]==1
    assert v["wins"]==1
    assert v["win_rate_pct"]==100.0
    assert v["expectancy_r"]==2.5

    print(
        "PASS strategy-version reporting"
    )

    print(
        "PASS realized PAPER P&L"
    )

    print(
        "PASS realized R calculation"
    )


    runtime.position_getter=lambda:[
        {
            "symbol":"TEST",
            "qty":10,
        },
        {
            "symbol":"ORPHAN",
            "qty":3,
        },
    ]

    recon=s.reconciliation()

    status={
        x["symbol"]:x["status"]
        for x in recon["positions"]
    }

    # TEST analytical outcome is T2_HIT, so ledger
    # no longer treats it as live. Broker still holds
    # it: correct classification is orphan.
    assert (
        status["TEST"]
        == "BROKER_POSITION_LEDGER_CLOSED"
    )

    assert (
        status["ORPHAN"]
        == "BROKER_POSITION_LEDGER_CLOSED"
    )

    print(
        "PASS broker/ledger orphan detection"
    )


print()
print("==============================")
print("V15.19 VALIDATION PASS")
print("==============================")
