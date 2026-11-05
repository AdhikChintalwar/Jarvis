from __future__ import annotations

import json
import math
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Query


router = APIRouter(
    prefix="/api/v1519",
    tags=["Baby V15.19 Strategy Analytics"],
)


class Runtime:
    position_getter = None


runtime = Runtime()


def configure_v1519_runtime(*, position_getter=None):
    runtime.position_getter = position_getter


def _f(v):
    try:
        return float(v)
    except Exception:
        return None


def _dt(v):
    if not v:
        return None
    try:
        x = datetime.fromisoformat(
            str(v).replace("Z", "+00:00")
        )
        if x.tzinfo is None:
            x = x.replace(tzinfo=timezone.utc)
        return x
    except Exception:
        return None


def _finite(v):
    x = _f(v)
    if x is None or not math.isfinite(x):
        return None
    return x


class StrategyAnalytics:
    def __init__(self, path="data/baby_ui.db"):
        self.path = Path(path)

    def _db(self):
        db = sqlite3.connect(
            self.path,
            timeout=30,
        )
        db.row_factory = sqlite3.Row
        return db

    def _table_exists(self, db, table):
        row = db.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type='table'
              AND name=?
            """,
            (table,),
        ).fetchone()

        return bool(row)

    def _columns(self, db, table):
        if not self._table_exists(db, table):
            return set()

        return {
            r["name"]
            for r in db.execute(
                f"PRAGMA table_info({table})"
            ).fetchall()
        }

    def trades(self, days=90):
        days = max(
            1,
            min(int(days or 90), 3650),
        )

        cutoff = (
            datetime.now(timezone.utc).timestamp()
            - days * 86400
        )

        with self._db() as db:
            if not self._table_exists(
                db,
                "v1511_forward_validation",
            ):
                return []

            rows = [
                dict(r)
                for r in db.execute(
                    """
                    SELECT *
                    FROM v1511_forward_validation
                    WHERE filled=1
                      AND quantity>0
                    ORDER BY id DESC
                    """
                ).fetchall()
            ]

            entry = {}

            if self._table_exists(
                db,
                "v1517_entry_confirmation",
            ):
                for r in db.execute(
                    """
                    SELECT *
                    FROM v1517_entry_confirmation
                    ORDER BY updated_at DESC
                    """
                ).fetchall():
                    d = dict(r)
                    key = (
                        str(d.get("symbol") or "").upper(),
                        int(d.get("ready_episode") or 0),
                    )
                    entry.setdefault(key, d)

            exits = {}

            if self._table_exists(
                db,
                "v1518_exit_state",
            ):
                for r in db.execute(
                    """
                    SELECT *
                    FROM v1518_exit_state
                    """
                ).fetchall():
                    d = dict(r)
                    exits[
                        (
                            str(d.get("symbol") or "").upper(),
                            int(d.get("ready_episode") or 0),
                        )
                    ] = d

        out = []

        for row in rows:
            created = _dt(
                row.get("first_fill_at")
                or row.get("t0")
            )

            if (
                created
                and created.timestamp() < cutoff
            ):
                continue

            symbol = str(
                row.get("symbol") or ""
            ).upper()

            episode = int(
                row.get("ready_episode") or 0
            )

            key = (symbol, episode)

            ec = entry.get(key)
            ex = exits.get(key)

            entry_v2 = bool(
                ec
                and str(
                    ec.get("strategy_version") or ""
                ).upper() == "ENTRY_V2"
                and str(
                    ec.get("state") or ""
                ).upper() == "CONFIRMED"
            )

            exit_v2 = bool(ex)

            strategy = (
                "ENTRY_V2+EXIT_V2"
                if entry_v2 and exit_v2
                else "ENTRY_V2"
                if entry_v2
                else "LEGACY"
            )

            fill = _finite(
                row.get("fill_price")
                or row.get("entry")
            )

            stop = _finite(
                row.get("invalidation")
            )

            original_qty = _finite(
                (ex or {}).get(
                    "original_quantity"
                )
            )

            if original_qty is None:
                original_qty = _finite(
                    row.get("quantity")
                )

            t1_qty = _finite(
                (ex or {}).get(
                    "t1_filled_qty"
                )
            ) or 0.0

            t1_price = _finite(
                (ex or {}).get(
                    "t1_fill_price"
                )
            )

            final_qty = _finite(
                (ex or {}).get(
                    "final_filled_qty"
                )
            ) or 0.0

            final_price = _finite(
                (ex or {}).get(
                    "final_fill_price"
                )
            )

            realized_pnl = None
            realized_r = None

            if fill is not None:
                components = []
                known_qty = 0.0

                if (
                    t1_qty > 0
                    and t1_price is not None
                ):
                    components.append(
                        t1_qty * (
                            t1_price - fill
                        )
                    )
                    known_qty += t1_qty

                if (
                    final_qty > 0
                    and final_price is not None
                ):
                    components.append(
                        final_qty * (
                            final_price - fill
                        )
                    )
                    known_qty += final_qty

                if components:
                    realized_pnl = round(
                        sum(components),
                        4,
                    )

                    if (
                        original_qty
                        and original_qty > 0
                        and stop is not None
                        and fill > stop
                    ):
                        initial_risk = (
                            original_qty
                            * (fill - stop)
                        )

                        if initial_risk > 0:
                            realized_r = round(
                                realized_pnl
                                / initial_risk,
                                4,
                            )

            diagnostics = {}

            if ec:
                try:
                    diagnostics = json.loads(
                        ec.get(
                            "diagnostics_json"
                        ) or "{}"
                    )
                except Exception:
                    diagnostics = {}

            out.append(
                {
                    "symbol": symbol,
                    "ready_episode": episode,
                    "strategy_version": strategy,

                    "entry_quality_score":
                        _finite(
                            (ec or {}).get(
                                "entry_quality_score"
                            )
                        ),

                    "entry_confirmation_state":
                        (ec or {}).get("state"),

                    "entry_diagnostics":
                        diagnostics,

                    "fill_price": fill,
                    "initial_stop": stop,
                    "target1":
                        _finite(
                            row.get("target1")
                        ),
                    "target2":
                        _finite(
                            row.get("target2")
                        ),

                    "original_quantity":
                        original_qty,

                    "price_path_outcome":
                        row.get("paper_outcome"),

                    "paper_mfe_pct":
                        _finite(
                            row.get(
                                "paper_mfe_pct"
                            )
                        ),
                    "paper_mae_pct":
                        _finite(
                            row.get(
                                "paper_mae_pct"
                            )
                        ),

                    "exit_state":
                        (ex or {}).get("state"),

                    "highest_r":
                        _finite(
                            (ex or {}).get(
                                "highest_r"
                            )
                        ),

                    "protected_stop":
                        _finite(
                            (ex or {}).get(
                                "protected_stop"
                            )
                        ),

                    "remaining_quantity":
                        _finite(
                            (ex or {}).get(
                                "remaining_quantity"
                            )
                        ),

                    "t1_filled_qty":
                        t1_qty,

                    "t1_fill_price":
                        t1_price,

                    "final_filled_qty":
                        final_qty,

                    "final_fill_price":
                        final_price,

                    "final_reason":
                        (ex or {}).get(
                            "final_reason"
                        ),

                    "broker_closed":
                        str(
                            (ex or {}).get(
                                "state"
                            ) or ""
                        ).upper()
                        in {
                            "CLOSED",
                            "CLOSED_BROKER_ZERO",
                        },

                    "realized_pnl":
                        realized_pnl,

                    "realized_r":
                        realized_r,

                    "first_fill_at":
                        row.get(
                            "first_fill_at"
                        ),

                    "paper_closed_at":
                        row.get(
                            "paper_closed_at"
                        ),

                    "exit_updated_at":
                        (ex or {}).get(
                            "updated_at"
                        ),
                }
            )

        return out

    def overview(self, days=90):
        rows = self.trades(days)

        versions = {}

        for r in rows:
            versions.setdefault(
                r["strategy_version"],
                [],
            ).append(r)

        by_version = {}

        for version, group in versions.items():
            resolved = [
                r for r in group
                if r["realized_r"] is not None
            ]

            wins = [
                r for r in resolved
                if r["realized_r"] > 0
            ]

            losses = [
                r for r in resolved
                if r["realized_r"] < 0
            ]

            rs = [
                r["realized_r"]
                for r in resolved
            ]

            pnls = [
                r["realized_pnl"]
                for r in resolved
                if r["realized_pnl"]
                is not None
            ]

            gross_profit = sum(
                p for p in pnls if p > 0
            )

            gross_loss = abs(
                sum(
                    p for p in pnls
                    if p < 0
                )
            )

            profit_factor = (
                round(
                    gross_profit
                    / gross_loss,
                    3,
                )
                if gross_loss > 0
                else None
            )

            by_version[version] = {
                "trades": len(group),
                "resolved": len(resolved),

                "wins": len(wins),
                "losses": len(losses),

                "win_rate_pct":
                    round(
                        100 * len(wins)
                        / len(resolved),
                        2,
                    )
                    if resolved
                    else None,

                "expectancy_r":
                    round(
                        sum(rs) / len(rs),
                        4,
                    )
                    if rs
                    else None,

                "total_realized_r":
                    round(
                        sum(rs),
                        4,
                    )
                    if rs
                    else None,

                "total_realized_pnl":
                    round(
                        sum(pnls),
                        2,
                    )
                    if pnls
                    else None,

                "profit_factor":
                    profit_factor,

                "t1_partial_filled":
                    sum(
                        1
                        for r in group
                        if (
                            r["t1_filled_qty"]
                            or 0
                        ) > 0
                    ),

                "t2_exits":
                    sum(
                        1
                        for r in group
                        if r["final_reason"]
                        == "T2_TARGET"
                    ),

                "protected_exits":
                    sum(
                        1
                        for r in group
                        if r["final_reason"]
                        == "PROTECTED_STOP"
                    ),

                "original_stop_exits":
                    sum(
                        1
                        for r in group
                        if r["final_reason"]
                        == "ORIGINAL_INVALIDATION"
                    ),
            }

        return {
            "days": int(days),
            "total_trades": len(rows),
            "by_strategy_version":
                by_version,
            "real_money_execution":
                "DISABLED",
        }

    def reconciliation(self):
        with self._db() as db:
            if not self._table_exists(
                db,
                "v1511_forward_validation",
            ):
                ledger = []
            else:
                ledger = [
                    dict(r)
                    for r in db.execute(
                        """
                        SELECT
                            symbol,
                            ready_episode,
                            quantity,
                            paper_outcome,
                            fill_price
                        FROM v1511_forward_validation
                        WHERE filled=1
                          AND quantity>0
                        ORDER BY symbol,
                                 ready_episode
                        """
                    ).fetchall()
                ]

        live = {}

        historical = {}

        for r in ledger:
            symbol = str(
                r.get("symbol") or ""
            ).upper()

            historical.setdefault(
                symbol,
                [],
            ).append(r)

            if str(
                r.get("paper_outcome")
                or ""
            ).upper() in {
                "OPEN",
                "T1_HIT",
            }:
                live.setdefault(
                    symbol,
                    [],
                ).append(r)

        broker = {}
        broker_error = None

        getter = runtime.position_getter

        if getter:
            try:
                for p in getter() or []:
                    if not isinstance(p, dict):
                        continue

                    symbol = str(
                        p.get("symbol")
                        or ""
                    ).upper()

                    qty = _finite(
                        p.get("qty")
                    ) or 0.0

                    if symbol:
                        broker[symbol] = {
                            **p,
                            "qty": qty,
                        }

            except Exception as exc:
                broker_error = (
                    f"{type(exc).__name__}: "
                    f"{exc}"
                )
        else:
            broker_error = (
                "POSITION_GETTER_NOT_CONFIGURED"
            )

        symbols = sorted(
            set(historical)
            | set(broker)
        )

        rows = []

        counts = {}

        for symbol in symbols:
            episodes = live.get(
                symbol,
                [],
            )

            live_qty = sum(
                _finite(
                    x.get("quantity")
                ) or 0
                for x in episodes
            )

            broker_qty = _finite(
                broker.get(
                    symbol,
                    {},
                ).get("qty")
            ) or 0.0

            if broker_error:
                status = "BROKER_UNKNOWN"

            elif len(episodes) > 1:
                status = (
                    "MULTIPLE_LIVE_EPISODES"
                )

            elif (
                live_qty == 0
                and broker_qty > 0
            ):
                status = (
                    "BROKER_POSITION_LEDGER_CLOSED"
                )

            elif (
                live_qty > 0
                and broker_qty == 0
            ):
                status = (
                    "LEDGER_OPEN_BROKER_ZERO"
                )

            elif abs(
                live_qty - broker_qty
            ) > max(
                0.0001,
                live_qty * 0.001,
            ):
                status = "QUANTITY_MISMATCH"

            else:
                status = "MATCH"

            counts[status] = (
                counts.get(status, 0)
                + 1
            )

            rows.append(
                {
                    "symbol": symbol,
                    "status": status,

                    "live_episodes": [
                        x.get(
                            "ready_episode"
                        )
                        for x in episodes
                    ],

                    "ledger_live_quantity":
                        round(
                            live_qty,
                            6,
                        ),

                    "broker_quantity":
                        round(
                            broker_qty,
                            6,
                        ),

                    "difference":
                        round(
                            broker_qty
                            - live_qty,
                            6,
                        ),

                    "historical_filled_episodes":
                        len(
                            historical.get(
                                symbol,
                                [],
                            )
                        ),
                }
            )

        return {
            "broker_error":
                broker_error,

            "summary":
                counts,

            "positions":
                rows,

            "real_money_execution":
                "DISABLED",
        }


service = StrategyAnalytics()


@router.get("/overview")
def overview(
    days: int = Query(
        90,
        ge=1,
        le=3650,
    )
):
    return service.overview(days)


@router.get("/trades")
def trades(
    days: int = Query(
        90,
        ge=1,
        le=3650,
    )
):
    return {
        "days": days,
        "trades":
            service.trades(days),
        "real_money_execution":
            "DISABLED",
    }


@router.get("/reconciliation")
def reconciliation():
    return service.reconciliation()
