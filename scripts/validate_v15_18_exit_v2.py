import os
import tempfile
from pathlib import Path

os.environ["BABY_EXIT_V2_PROTECT_ARM_R"] = "0.75"
os.environ["BABY_EXIT_V2_PROTECT_R"] = "1.00"
os.environ["BABY_EXIT_V2_PROTECTED_STOP_R"] = "-0.05"
os.environ["BABY_EXIT_V2_POST_T1_STOP_R"] = "0.10"
os.environ["BABY_EXIT_V2_T1_FRACTION"] = "0.50"

from baby_ui_backend.v1515_autopilot_worker import PaperAutopilotWorker


class QuoteFeed:
    def __init__(self, price):
        self.price = price

    def __call__(self, symbol):
        return {"price": self.price}


def make_worker(db_path, quote, broker_qty_ref, submitted, orders):
    def submitter(**kwargs):
        submitted.append(kwargs)
        return {
            "id": f"order-{len(submitted)}",
            "status": "ACCEPTED",
            "symbol": kwargs["symbol"],
            "side": kwargs["side"],
            "qty": kwargs["quantity"],
        }

    def positions():
        qty = broker_qty_ref["qty"]
        if qty <= 0:
            return []
        return [{"symbol": "TEST", "qty": qty}]

    return PaperAutopilotWorker(
        db_path=db_path,
        proposal_getter=lambda s: {},
        quote_getter=quote,
        account_getter=lambda: {},
        order_submitter=submitter,
        ledger=None,
        position_getter=positions,
        order_getter=lambda limit=200: orders,
        research_getter=lambda s: {},
        notifier=None,
        interval_seconds=5,
    )


def seed(w):
    with w._db() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS v1515_actions(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT,
            episode_key TEXT,
            action TEXT NOT NULL,
            reason TEXT NOT NULL,
            payload_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS v1511_forward_validation(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT,
            ready_episode INTEGER,
            filled INTEGER,
            quantity REAL,
            paper_outcome TEXT,
            fill_price REAL,
            entry REAL,
            invalidation REAL,
            target1 REAL,
            target2 REAL
        );
        """)

        db.execute("""
            INSERT INTO v1511_forward_validation(
                symbol,ready_episode,filled,quantity,paper_outcome,
                fill_price,entry,invalidation,target1,target2
            )
            VALUES('TEST',1,1,10,'OPEN',100,100,99,102,103)
        """)

        db.execute("""
            INSERT OR REPLACE INTO v1517_entry_confirmation(
                symbol,ready_episode,strategy_version,state,armed_at,
                first_price,low_price,high_price,last_price,
                observations,improving_count,rebound_r,
                entry_quality_score,block_reason,
                diagnostics_json,updated_at
            )
            VALUES(
                'TEST',1,'ENTRY_V2','CONFIRMED',
                '2026-11-05T00:00:00+00:00',
                100,99.8,100.1,100.1,
                4,2,0.3,90,NULL,'{}',
                '2026-11-05T00:00:00+00:00'
            )
        """)
        db.commit()

    return {
        "symbol": "TEST",
        "ready_episode": 1,
        "filled": 1,
        "quantity": 10,
        "paper_outcome": "OPEN",
        "fill_price": 100,
        "entry": 100,
        "invalidation": 99,
        "target1": 102,
        "target2": 103,
    }


# 1: 0.50R no sell
with tempfile.TemporaryDirectory() as td:
    submitted, orders = [], []
    broker = {"qty": 10}
    q = QuoteFeed(100.50)
    w = make_worker(Path(td)/"t1.db", q, broker, submitted, orders)
    row = seed(w)

    w._exit_if_needed(row)

    assert submitted == []
    assert round(float(w._exit_state("TEST",1)["highest_r"]),2) == 0.50

print("PASS 1: 0.50R does not sell")


# 2: 0.80R protection armed
with tempfile.TemporaryDirectory() as td:
    submitted, orders = [], []
    broker = {"qty": 10}
    q = QuoteFeed(100.80)
    w = make_worker(Path(td)/"t2.db", q, broker, submitted, orders)
    row = seed(w)

    w._exit_if_needed(row)

    assert submitted == []
    assert w._exit_state("TEST",1)["state"] == "PROTECTION_ARMED"

print("PASS 2: 0.80R arms protection without selling")


# 3: +1.10R protected stop
with tempfile.TemporaryDirectory() as td:
    submitted, orders = [], []
    broker = {"qty": 10}
    q = QuoteFeed(101.10)
    w = make_worker(Path(td)/"t3.db", q, broker, submitted, orders)
    row = seed(w)

    w._exit_if_needed(row)

    s = w._exit_state("TEST",1)

    assert submitted == []
    assert s["state"] == "PROTECTED"
    assert round(float(s["protected_stop"]),2) == 99.95

print("PASS 3: +1R creates protected stop")


# 4: T1 50% partial
with tempfile.TemporaryDirectory() as td:
    submitted, orders = [], []
    broker = {"qty": 10}
    q = QuoteFeed(102.00)
    w = make_worker(Path(td)/"t4.db", q, broker, submitted, orders)
    row = seed(w)

    w._exit_if_needed(row)

    assert len(submitted) == 1
    assert submitted[0]["side"] == "SELL"
    assert submitted[0]["quantity"] == 5.0
    assert w._exit_state("TEST",1)["state"] == "T1_PARTIAL_SUBMITTED"

print("PASS 4: T1 submits exactly 50% partial SELL")


# 5: T1 fill reconciliation
with tempfile.TemporaryDirectory() as td:
    submitted, orders = [], []
    broker = {"qty": 10}
    q = QuoteFeed(102.00)
    w = make_worker(Path(td)/"t5.db", q, broker, submitted, orders)
    row = seed(w)

    w._exit_if_needed(row)

    oid = w._exit_state("TEST",1)["t1_order_id"]

    orders.append({
        "id": oid,
        "status": "FILLED",
        "qty": 5,
        "filled_qty": 5,
    })

    broker["qty"] = 5
    s = w._reconcile_exit_state(row, 5)

    assert s["t1_filled_qty"] == 5
    assert s["remaining_quantity"] == 5
    assert s["state"] == "T1_PARTIAL_FILLED"

print("PASS 5: T1 partial fill reconciles")


# 6: T2 remaining sell
with tempfile.TemporaryDirectory() as td:
    submitted, orders = [], []
    broker = {"qty": 10}
    q = QuoteFeed(102.00)
    w = make_worker(Path(td)/"t6.db", q, broker, submitted, orders)
    row = seed(w)

    w._exit_if_needed(row)

    oid = w._exit_state("TEST",1)["t1_order_id"]

    orders.append({
        "id": oid,
        "status": "FILLED",
        "qty": 5,
        "filled_qty": 5,
    })

    broker["qty"] = 5
    w._reconcile_exit_state(row,5)

    guard = w._exit_reconciliation_guard(row,5)

    assert guard["eligible"] is True
    assert guard["expected_qty"] == 5
    assert guard["quantity_source"] == "EXIT_V2_REMAINING"

    q.price = 103.00
    w._exit_if_needed(row)

    assert len(submitted) == 2
    assert submitted[1]["quantity"] == 5.0

    s = w._exit_state("TEST",1)
    assert s["final_reason"] == "T2_TARGET"

print("PASS 6: T2 sells remaining broker quantity")


# 7: +1R reversal protected stop
with tempfile.TemporaryDirectory() as td:
    submitted, orders = [], []
    broker = {"qty": 10}
    q = QuoteFeed(101.10)
    w = make_worker(Path(td)/"t7.db", q, broker, submitted, orders)
    row = seed(w)

    w._exit_if_needed(row)
    assert submitted == []

    q.price = 99.94
    w._exit_if_needed(row)

    assert len(submitted) == 1
    assert submitted[0]["quantity"] == 10
    assert w._exit_state("TEST",1)["final_reason"] == "PROTECTED_STOP"

print("PASS 7: +1R reversal triggers protected exit")


# 8: original stop
with tempfile.TemporaryDirectory() as td:
    submitted, orders = [], []
    broker = {"qty": 10}
    q = QuoteFeed(98.95)
    w = make_worker(Path(td)/"t8.db", q, broker, submitted, orders)
    row = seed(w)

    w._exit_if_needed(row)

    assert len(submitted) == 1
    assert submitted[0]["quantity"] == 10
    assert w._exit_state("TEST",1)["final_reason"] == "ORIGINAL_INVALIDATION"

print("PASS 8: original invalidation exits full broker position")


# 9: broker unknown
with tempfile.TemporaryDirectory() as td:
    submitted, orders = [], []

    def bad_positions():
        raise RuntimeError("broker unavailable")

    q = QuoteFeed(98.50)

    w = PaperAutopilotWorker(
        db_path=Path(td)/"t9.db",
        proposal_getter=lambda s:{},
        quote_getter=q,
        account_getter=lambda:{},
        order_submitter=lambda **kwargs: submitted.append(kwargs),
        ledger=None,
        position_getter=bad_positions,
        order_getter=lambda limit=200:orders,
        research_getter=lambda s:{},
        notifier=None,
        interval_seconds=5,
    )

    row=seed(w)
    w._exit_if_needed(row)

    assert submitted == []

print("PASS 9: unknown broker position fails closed")


# 10: multiple live episodes
with tempfile.TemporaryDirectory() as td:
    submitted, orders = [], []
    broker = {"qty": 20}
    q = QuoteFeed(98.50)

    w = make_worker(Path(td)/"t10.db", q, broker, submitted, orders)
    row = seed(w)

    with w._db() as db:
        db.execute("""
            INSERT INTO v1511_forward_validation(
                symbol,ready_episode,filled,quantity,paper_outcome,
                fill_price,entry,invalidation,target1,target2
            )
            VALUES('TEST',2,1,10,'OPEN',100,100,99,102,103)
        """)

        db.execute("""
            INSERT OR REPLACE INTO v1517_entry_confirmation(
                symbol,ready_episode,strategy_version,state,armed_at,
                first_price,low_price,high_price,last_price,
                observations,improving_count,rebound_r,
                entry_quality_score,block_reason,
                diagnostics_json,updated_at
            )
            VALUES(
                'TEST',2,'ENTRY_V2','CONFIRMED',
                '2026-11-05T00:00:00+00:00',
                100,99.8,100.1,100.1,
                4,2,0.3,90,NULL,'{}',
                '2026-11-05T00:00:00+00:00'
            )
        """)
        db.commit()

    w._exit_if_needed(row)

    assert submitted == []

print("PASS 10: multiple episodes block autonomous SELL")


# 11: submit unknown must not retry
with tempfile.TemporaryDirectory() as td:
    attempts = []
    q = QuoteFeed(98.50)

    def bad_submit(**kwargs):
        attempts.append(kwargs)
        raise RuntimeError("timeout")

    w = PaperAutopilotWorker(
        db_path=Path(td)/"t11.db",
        proposal_getter=lambda s:{},
        quote_getter=q,
        account_getter=lambda:{},
        order_submitter=bad_submit,
        ledger=None,
        position_getter=lambda:[{"symbol":"TEST","qty":10}],
        order_getter=lambda limit=200:[],
        research_getter=lambda s:{},
        notifier=None,
        interval_seconds=5,
    )

    row = seed(w)

    w._exit_if_needed(row)
    w._exit_if_needed(row)

    assert len(attempts) == 1
    assert w._exit_state("TEST",1)["state"] == "FINAL_EXIT_SUBMIT_UNKNOWN"

print("PASS 11: unknown submit outcome is not automatically retried")

print()
print("====================================")
print("EXIT ENGINE V2 REGRESSION SUITE PASS")
print("====================================")
