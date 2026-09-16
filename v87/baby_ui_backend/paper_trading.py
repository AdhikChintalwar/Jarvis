from __future__ import annotations

import json
import os
import sqlite3
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class PaperOrder:
    id: str
    symbol: str
    side: str
    quantity: float
    order_type: str
    status: str
    submitted_at: str
    limit_price: float | None = None
    filled_quantity: float = 0.0
    average_fill_price: float | None = None
    fee: float = 0.0
    quote_source: str | None = None
    quote_quality: str | None = None
    quote_as_of: str | None = None
    note: str | None = None


class PaperTradingService:
    """Persistent forward paper broker. It contains no brokerage integration."""

    def __init__(self, path: str = "data/baby_paper_trading.db"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.starting_cash = float(os.getenv("BABY_PAPER_STARTING_CASH", "100000"))
        self.fee_bps = float(os.getenv("BABY_PAPER_FEE_BPS", "0"))
        self.slippage_bps = float(os.getenv("BABY_PAPER_SLIPPAGE_BPS", "5"))
        self._lock = RLock()
        self._init_db()

    def _connect(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        return db

    def _init_db(self):
        with self._connect() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS paper_account(
              id INTEGER PRIMARY KEY CHECK(id=1),
              starting_cash REAL NOT NULL,
              cash REAL NOT NULL,
              realized_pnl REAL NOT NULL DEFAULT 0,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS paper_positions(
              symbol TEXT PRIMARY KEY,
              quantity REAL NOT NULL,
              average_cost REAL NOT NULL,
              realized_pnl REAL NOT NULL DEFAULT 0,
              updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS paper_orders(
              id TEXT PRIMARY KEY,
              symbol TEXT NOT NULL,
              side TEXT NOT NULL,
              quantity REAL NOT NULL,
              order_type TEXT NOT NULL,
              limit_price REAL,
              status TEXT NOT NULL,
              submitted_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              filled_quantity REAL NOT NULL DEFAULT 0,
              average_fill_price REAL,
              fee REAL NOT NULL DEFAULT 0,
              quote_source TEXT,
              quote_quality TEXT,
              quote_as_of TEXT,
              note TEXT
            );
            CREATE TABLE IF NOT EXISTS paper_fills(
              id TEXT PRIMARY KEY,
              order_id TEXT NOT NULL,
              symbol TEXT NOT NULL,
              side TEXT NOT NULL,
              quantity REAL NOT NULL,
              price REAL NOT NULL,
              notional REAL NOT NULL,
              fee REAL NOT NULL,
              slippage_bps REAL NOT NULL,
              quote_price REAL NOT NULL,
              quote_source TEXT,
              quote_quality TEXT,
              quote_as_of TEXT,
              filled_at TEXT NOT NULL,
              FOREIGN KEY(order_id) REFERENCES paper_orders(id)
            );
            CREATE TABLE IF NOT EXISTS paper_equity_snapshots(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              equity REAL NOT NULL,
              cash REAL NOT NULL,
              positions_value REAL NOT NULL,
              unrealized_pnl REAL NOT NULL,
              quote_map TEXT NOT NULL,
              created_at TEXT NOT NULL
            );
            """)
            row = db.execute("SELECT 1 FROM paper_account WHERE id=1").fetchone()
            if not row:
                now = utcnow()
                db.execute(
                    "INSERT INTO paper_account(id,starting_cash,cash,created_at,updated_at) VALUES(1,?,?,?,?)",
                    (self.starting_cash, self.starting_cash, now, now),
                )
            db.commit()

    def reset(self, starting_cash: float | None = None):
        cash = float(starting_cash if starting_cash is not None else self.starting_cash)
        if cash <= 0:
            raise ValueError("starting_cash must be positive")
        with self._lock, self._connect() as db:
            db.execute("DELETE FROM paper_fills")
            db.execute("DELETE FROM paper_orders")
            db.execute("DELETE FROM paper_positions")
            db.execute("DELETE FROM paper_equity_snapshots")
            now = utcnow()
            db.execute(
                "UPDATE paper_account SET starting_cash=?,cash=?,realized_pnl=0,updated_at=? WHERE id=1",
                (cash, cash, now),
            )
            db.commit()
        return self.snapshot({})

    def submit_order(self, symbol: str, side: str, quantity: float, order_type: str = "MARKET", limit_price: float | None = None, note: str | None = None):
        symbol = symbol.strip().upper()
        side = side.strip().upper()
        order_type = order_type.strip().upper()
        quantity = float(quantity)
        if not symbol or not symbol.replace(".", "").replace("-", "").isalnum():
            raise ValueError("invalid symbol")
        if side not in {"BUY", "SELL"}:
            raise ValueError("side must be BUY or SELL")
        if order_type not in {"MARKET", "LIMIT"}:
            raise ValueError("order_type must be MARKET or LIMIT")
        if quantity <= 0:
            raise ValueError("quantity must be positive")
        if order_type == "LIMIT" and (limit_price is None or float(limit_price) <= 0):
            raise ValueError("positive limit_price required for LIMIT order")
        now = utcnow()
        order = PaperOrder(str(uuid.uuid4()), symbol, side, quantity, order_type, "PENDING", now, float(limit_price) if limit_price is not None else None, note=note)
        with self._lock, self._connect() as db:
            db.execute("""INSERT INTO paper_orders(id,symbol,side,quantity,order_type,limit_price,status,submitted_at,updated_at,note)
                        VALUES(?,?,?,?,?,?,?,?,?,?)""",
                       (order.id,order.symbol,order.side,order.quantity,order.order_type,order.limit_price,order.status,now,now,note))
            db.commit()
        return asdict(order)

    def execute(self, order_id: str, quote: dict[str, Any]):
        """Execute a pending PAPER order against a supplied quote. Never contacts a broker."""
        qpx = quote.get("price")
        if qpx is None or float(qpx) <= 0:
            raise ValueError("A valid market quote is required to fill a paper order")
        qpx = float(qpx)
        quality = str(quote.get("quality") or "UNKNOWN").upper()
        source = str(quote.get("source") or "UNKNOWN")
        as_of = quote.get("as_of") or quote.get("timestamp")
        with self._lock, self._connect() as db:
            row = db.execute("SELECT * FROM paper_orders WHERE id=?", (order_id,)).fetchone()
            if not row:
                raise KeyError("paper order not found")
            o = dict(row)
            if o["status"] != "PENDING":
                return o
            if o["order_type"] == "LIMIT":
                lp = float(o["limit_price"])
                if o["side"] == "BUY" and qpx > lp:
                    return {**o, "message": "BUY limit not reached"}
                if o["side"] == "SELL" and qpx < lp:
                    return {**o, "message": "SELL limit not reached"}
            slip = self.slippage_bps / 10000.0
            fill_px = qpx * (1 + slip if o["side"] == "BUY" else 1 - slip)
            qty = float(o["quantity"])
            notional = qty * fill_px
            fee = notional * self.fee_bps / 10000.0
            acct = dict(db.execute("SELECT * FROM paper_account WHERE id=1").fetchone())
            posrow = db.execute("SELECT * FROM paper_positions WHERE symbol=?", (o["symbol"],)).fetchone()
            pos = dict(posrow) if posrow else {"quantity":0.0,"average_cost":0.0,"realized_pnl":0.0}
            status = "FILLED"
            realized_delta = 0.0
            if o["side"] == "BUY":
                if notional + fee > float(acct["cash"]):
                    status = "REJECTED_INSUFFICIENT_CASH"
                else:
                    oldq = float(pos["quantity"]); newq = oldq + qty
                    avg = ((oldq * float(pos["average_cost"])) + notional + fee) / newq
                    db.execute("""INSERT INTO paper_positions(symbol,quantity,average_cost,realized_pnl,updated_at)
                                  VALUES(?,?,?,?,?) ON CONFLICT(symbol) DO UPDATE SET quantity=excluded.quantity,average_cost=excluded.average_cost,updated_at=excluded.updated_at""",
                               (o["symbol"],newq,avg,float(pos["realized_pnl"]),utcnow()))
                    db.execute("UPDATE paper_account SET cash=cash-?,updated_at=? WHERE id=1", (notional+fee,utcnow()))
            else:
                if qty > float(pos["quantity"]):
                    status = "REJECTED_INSUFFICIENT_POSITION"
                else:
                    realized_delta = (fill_px - float(pos["average_cost"])) * qty - fee
                    newq = float(pos["quantity"]) - qty
                    if newq <= 1e-12:
                        db.execute("DELETE FROM paper_positions WHERE symbol=?", (o["symbol"],))
                    else:
                        db.execute("UPDATE paper_positions SET quantity=?,realized_pnl=realized_pnl+?,updated_at=? WHERE symbol=?", (newq,realized_delta,utcnow(),o["symbol"]))
                    db.execute("UPDATE paper_account SET cash=cash+?,realized_pnl=realized_pnl+?,updated_at=? WHERE id=1", (notional-fee,realized_delta,utcnow()))
            now = utcnow()
            db.execute("""UPDATE paper_orders SET status=?,updated_at=?,filled_quantity=?,average_fill_price=?,fee=?,quote_source=?,quote_quality=?,quote_as_of=? WHERE id=?""",
                       (status,now,qty if status=="FILLED" else 0,fill_px if status=="FILLED" else None,fee if status=="FILLED" else 0,source,quality,as_of,order_id))
            if status == "FILLED":
                db.execute("""INSERT INTO paper_fills(id,order_id,symbol,side,quantity,price,notional,fee,slippage_bps,quote_price,quote_source,quote_quality,quote_as_of,filled_at)
                              VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                           (str(uuid.uuid4()),order_id,o["symbol"],o["side"],qty,fill_px,notional,fee,self.slippage_bps,qpx,source,quality,as_of,now))
            db.commit()
            return dict(db.execute("SELECT * FROM paper_orders WHERE id=?", (order_id,)).fetchone())

    def snapshot(self, prices: dict[str, dict[str, Any]]):
        with self._connect() as db:
            account = dict(db.execute("SELECT * FROM paper_account WHERE id=1").fetchone())
            positions = [dict(r) for r in db.execute("SELECT * FROM paper_positions ORDER BY symbol")]
            orders = [dict(r) for r in db.execute("SELECT * FROM paper_orders ORDER BY submitted_at DESC LIMIT 200")]
            fills = [dict(r) for r in db.execute("SELECT * FROM paper_fills ORDER BY filled_at DESC LIMIT 200")]
        pv = 0.0; unreal = 0.0
        for p in positions:
            q = prices.get(p["symbol"], {}) if prices else {}
            mark = q.get("price")
            p["mark_price"] = mark
            p["quote_source"] = q.get("source")
            p["quote_quality"] = q.get("quality")
            p["quote_as_of"] = q.get("as_of") or q.get("timestamp")
            if mark is None:
                p["market_value"] = None; p["unrealized_pnl"] = None
                continue
            p["market_value"] = float(mark) * float(p["quantity"])
            p["unrealized_pnl"] = (float(mark)-float(p["average_cost"])) * float(p["quantity"])
            pv += p["market_value"]; unreal += p["unrealized_pnl"]
        equity = float(account["cash"]) + pv
        return {
            "status":"READY", "database":str(self.path), "mode":"FORWARD_PAPER_SIMULATION",
            "real_money_execution":"DISABLED", "brokerage_connection":"NONE",
            "account":{**account,"positions_value":pv,"unrealized_pnl":unreal,"equity":equity,"buying_power":float(account["cash"])},
            "positions":positions,"orders":orders,"fills":fills,
            "settings":{"slippage_bps":self.slippage_bps,"fee_bps":self.fee_bps},
        }
