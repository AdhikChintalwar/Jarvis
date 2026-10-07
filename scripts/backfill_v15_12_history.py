from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

DB = Path("data/baby_ui.db")


def map_snapshot(row):
    try:
        payload = json.loads(row["snapshot_json"] or "{}")
    except Exception:
        payload = {}

    symbol = str(row["symbol"] or "").upper().strip()
    observed_at = row["created_at"]

    raw_state = str(
        payload.get("setup_state")
        or row["setup_state"]
        or ""
    ).upper().strip()

    phase = str(
        payload.get("phase")
        or row["phase"]
        or ""
    ).upper().strip()

    ready = bool(payload.get("ready"))

    # Conservative reconstruction only.
    # Never infer SETUP_READY unless the historical record explicitly says ready.
    if ready:
        state = "SETUP_READY"
        score = 100

    elif raw_state in {
        "NEAR_READY",
    }:
        state = "NEAR_READY"
        score = 92

    elif raw_state in {
        "ACTIVE",
        "ACTIVE_SETUP",
        "ENTRY_ZONE",
        "AT_PULLBACK_ZONE",
        "BREAKOUT_TRIGGERED",
    }:
        state = "ACTIVE_SETUP"
        score = 72

    elif raw_state in {
        "SETUP_FORMING",
        "WAITING",
        "WAIT_FOR_PULLBACK_OR_BREAKOUT",
    }:
        state = "SETUP_FORMING"
        score = 58

    else:
        state = "MONITOR"
        score = 40

    setup_status = raw_state or phase or "UNKNOWN"

    reason = (
        "Historical V15.5 pipeline snapshot reconstructed conservatively "
        f"from persisted setup_state={setup_status}."
    )

    return {
        "symbol": symbol,
        "state": state,
        "score": score,
        "reason": reason,
        "setup_status": setup_status,
        "failures_json": "[]",
        "observed_at": observed_at,
        "source": "v155_pipeline_snapshots",
        "source_key": str(row["id"]),
    }


def map_v1510(row):
    return {
        "symbol": str(row["symbol"] or "").upper().strip(),
        "state": "MONITOR",
        "score": 40,
        "reason": (
            "Historical V15.10 opportunity observation. "
            "No later deterministic readiness state was persisted."
        ),
        "setup_status": "HISTORICAL_OPPORTUNITY",
        "failures_json": "[]",
        "observed_at": row["observed_at"],
        "source": "v1510_opportunity_trajectory",
        "source_key": (
            f'{row["symbol"]}:{row["observation_date"]}:{row["observed_at"]}'
        ),
    }


def ensure_schema(db):
    cols = {
        r["name"]
        for r in db.execute(
            "PRAGMA table_info(v1512_readiness_history)"
        ).fetchall()
    }

    if "source" not in cols:
        db.execute(
            "ALTER TABLE v1512_readiness_history ADD COLUMN source TEXT"
        )

    if "source_key" not in cols:
        db.execute(
            "ALTER TABLE v1512_readiness_history ADD COLUMN source_key TEXT"
        )

    db.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS
        idx_v1512_history_source_key
        ON v1512_readiness_history(source, source_key)
        WHERE source IS NOT NULL AND source_key IS NOT NULL
    """)


def insert_one(db, item):
    cur = db.execute("""
        INSERT OR IGNORE INTO v1512_readiness_history(
            symbol,
            state,
            readiness_potential,
            reason,
            setup_status,
            failures_json,
            observed_at,
            source,
            source_key
        )
        VALUES(?,?,?,?,?,?,?,?,?)
    """, (
        item["symbol"],
        item["state"],
        item["score"],
        item["reason"],
        item["setup_status"],
        item["failures_json"],
        item["observed_at"],
        item["source"],
        item["source_key"],
    ))

    return cur.rowcount == 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually write rows. Without this flag the script is dry-run only."
    )
    args = parser.parse_args()

    if not DB.exists():
        raise SystemExit(f"Database not found: {DB}")

    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row

    ensure_schema(db)

    candidates = []

    # Main historical source.
    rows = db.execute("""
        SELECT *
        FROM v155_pipeline_snapshots
        WHERE created_at IS NOT NULL
        ORDER BY created_at
    """).fetchall()

    candidates.extend(map_snapshot(r) for r in rows)

    # Older observations.
    rows = db.execute("""
        SELECT *
        FROM v1510_opportunity_trajectory
        WHERE observed_at IS NOT NULL
        ORDER BY observed_at
    """).fetchall()

    candidates.extend(map_v1510(r) for r in rows)

    existing = db.execute("""
        SELECT COUNT(*)
        FROM v1512_readiness_history
    """).fetchone()[0]

    print("Existing V15.12 history rows:", existing)
    print("Historical candidates:", len(candidates))

    by_state = {}
    by_source = {}

    for x in candidates:
        by_state[x["state"]] = by_state.get(x["state"], 0) + 1
        by_source[x["source"]] = by_source.get(x["source"], 0) + 1

    print("\nBy state:")
    for k, v in sorted(by_state.items()):
        print(f"  {k}: {v}")

    print("\nBy source:")
    for k, v in sorted(by_source.items()):
        print(f"  {k}: {v}")

    if not args.apply:
        db.rollback()
        print("\nDRY RUN ONLY")
        print("Run again with --apply to write the backfill.")
        db.close()
        return

    inserted = 0

    for item in candidates:
        if insert_one(db, item):
            inserted += 1

    db.commit()

    total = db.execute("""
        SELECT COUNT(*)
        FROM v1512_readiness_history
    """).fetchone()[0]

    print("\nInserted:", inserted)
    print("Skipped existing:", len(candidates) - inserted)
    print("Total V15.12 history rows:", total)
    print("Backfill complete.")

    db.close()


if __name__ == "__main__":
    main()
