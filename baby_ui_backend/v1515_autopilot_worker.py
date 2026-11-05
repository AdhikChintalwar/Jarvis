
from __future__ import annotations

import json, os, sqlite3, threading, time, urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

PAPER_CONFIRMATION = "EXECUTE ALPACA PAPER"

def _now():
    return datetime.now(timezone.utc).isoformat()

def _f(v):
    try:
        return float(v)
    except Exception:
        return None

class NtfyPush:
    def __init__(self):
        self.enabled = os.getenv("BABY_NTFY_ENABLED","false").lower()=="true"
        self.topic = (os.getenv("BABY_NTFY_TOPIC") or "").strip()
        self.base = (os.getenv("BABY_NTFY_BASE_URL") or "https://ntfy.sh").rstrip("/")

    def send(self, title, message, priority="high", tags="chart_with_upwards_trend"):
        if not (self.enabled and self.topic):
            return {"sent":False,"reason":"NTFY_DISABLED_OR_UNCONFIGURED"}
        req=urllib.request.Request(
            f"{self.base}/{self.topic}",
            data=message.encode(),
            method="POST",
            headers={"Title":title,"Priority":priority,"Tags":tags}
        )
        with urllib.request.urlopen(req, timeout=8) as r:
            return {"sent":200 <= r.status < 300,"status":r.status}

class PaperAutopilotWorker:
    """
    Autonomous Alpaca PAPER entry/exit worker.

    Safety:
      - PAPER broker callback only
      - max 20% allocation per entry
      - risk-to-stop can reduce size
      - max 3 new entries/day
      - no chase when proposal no longer ELIGIBLE
      - only sells positions tracked in v1511_forward_validation
      - real money has no route here
    """
    def __init__(
        self, db_path, proposal_getter, quote_getter, account_getter,
        order_submitter, ledger, position_getter=None,
        order_getter=None,
        research_getter=None,
        notifier=None, interval_seconds=5
    ):
        self.db_path=Path(db_path)
        self.proposal_getter=proposal_getter
        self.quote_getter=quote_getter
        self.account_getter=account_getter
        self.order_submitter=order_submitter
        self.position_getter=position_getter
        self.order_getter=order_getter
        self.research_getter=research_getter
        self.ledger=ledger
        self.notifier=notifier
        self.push=NtfyPush()
        self.interval=max(2,int(interval_seconds))
        self.stop_event=threading.Event()
        self.thread=None
        self.max_alloc=float(os.getenv("BABY_PAPER_MAX_ALLOCATION_PCT","0.20"))
        self.max_trades=int(os.getenv("BABY_PAPER_MAX_NEW_TRADES_PER_DAY","3"))
        self.max_risk=float(os.getenv("BABY_PAPER_MAX_PORTFOLIO_RISK_PCT","0.01"))
        self.enabled=os.getenv("BABY_PAPER_AUTOPILOT_ENABLED","true").lower()=="true"

        # V15.17 Entry Engine V2
        self.entry_min_score=float(os.getenv("BABY_ENTRY_V2_MIN_SCORE","70"))
        self.entry_min_observations=max(3,int(os.getenv("BABY_ENTRY_V2_MIN_OBSERVATIONS","4")))
        self.entry_min_seconds=max(0,int(os.getenv("BABY_ENTRY_V2_MIN_SECONDS","15")))
        self.entry_min_rebound_r=float(os.getenv("BABY_ENTRY_V2_MIN_REBOUND_R","0.12"))
        self.entry_structure_lock_days=max(1,int(os.getenv("BABY_ENTRY_V2_STRUCTURE_LOCK_DAYS","7")))
        self._ensure_entry_engine_tables()
        self._ensure_exit_engine_tables()

        # V15.18 Exit Engine V2
        self.exit_protect_arm_r=float(
            os.getenv("BABY_EXIT_V2_PROTECT_ARM_R","0.75")
        )
        self.exit_protect_r=float(
            os.getenv("BABY_EXIT_V2_PROTECT_R","1.00")
        )
        self.exit_protected_stop_r=float(
            os.getenv("BABY_EXIT_V2_PROTECTED_STOP_R","-0.05")
        )
        self.exit_post_t1_stop_r=float(
            os.getenv("BABY_EXIT_V2_POST_T1_STOP_R","0.10")
        )
        self.exit_t1_fraction=max(
            0.05,
            min(
                1.0,
                float(os.getenv("BABY_EXIT_V2_T1_FRACTION","0.50"))
            )
        )

    def _ensure_entry_engine_tables(self):
        with sqlite3.connect(self.db_path) as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS v1517_entry_confirmation(
                    symbol TEXT NOT NULL,
                    ready_episode INTEGER NOT NULL,
                    strategy_version TEXT NOT NULL,
                    state TEXT NOT NULL,
                    armed_at TEXT NOT NULL,
                    first_price REAL,
                    low_price REAL,
                    high_price REAL,
                    last_price REAL,
                    observations INTEGER NOT NULL DEFAULT 0,
                    improving_count INTEGER NOT NULL DEFAULT 0,
                    rebound_r REAL,
                    entry_quality_score REAL,
                    block_reason TEXT,
                    diagnostics_json TEXT NOT NULL DEFAULT '{}',
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(symbol,ready_episode)
                )
            """)
            db.execute("""
                CREATE INDEX IF NOT EXISTS idx_v1517_entry_state
                ON v1517_entry_confirmation(state,updated_at)
            """)
            db.commit()

    @staticmethod
    def _level_close(a,b,tolerance=0.0075):
        a=_f(a); b=_f(b)
        if a is None or b is None:
            return False
        scale=max(abs(a),abs(b),1e-9)
        return abs(a-b)/scale <= tolerance

    def _failed_setup_lock(self,row):
        """
        Prevent immediate re-entry into essentially the same failed structure.

        This is deliberately based on stop/T1/T2 structure instead of ticker
        alone. A materially changed setup may trade again.
        """
        symbol=str(row.get("symbol") or "").upper()
        stop=_f(row.get("invalidation"))
        t1=_f(row.get("target1"))
        t2=_f(row.get("target2"))

        if not symbol or None in (stop,t1,t2):
            return None

        cutoff=(
            datetime.now(timezone.utc)
            - timedelta(days=self.entry_structure_lock_days)
        ).isoformat()

        try:
            with self._db() as db:
                rows=db.execute("""
                    SELECT id,ready_episode,t0,invalidation,target1,target2,
                           paper_outcome
                    FROM v1511_forward_validation
                    WHERE symbol=?
                      AND filled=1
                      AND paper_outcome IN ('STOPPED','T1_THEN_STOP')
                      AND t0>=?
                    ORDER BY id DESC
                    LIMIT 20
                """,(symbol,cutoff)).fetchall()

            for old in rows:
                old=dict(old)

                same=(
                    self._level_close(stop,old.get("invalidation"))
                    and self._level_close(t1,old.get("target1"))
                    and self._level_close(t2,old.get("target2"))
                )

                if same:
                    return {
                        "blocked":True,
                        "reason":"RECENT_FAILED_STRUCTURE_MATCH",
                        "prior_episode":old.get("ready_episode"),
                        "prior_t0":old.get("t0"),
                        "prior_outcome":old.get("paper_outcome"),
                    }

        except Exception as exc:
            # Re-entry safety must fail closed.
            return {
                "blocked":True,
                "reason":"FAILED_STRUCTURE_LOOKUP_UNKNOWN",
                "error":str(exc),
            }

        return None

    def _research_snapshot(self,symbol):
        if not self.research_getter:
            return {}

        try:
            d=self.research_getter(symbol)
            return d if isinstance(d,dict) else {}
        except Exception:
            return {}

    def _entry_confirmation(self,row,proposal,px):
        """
        V15.17 live long-entry confirmation.

        Research says WHAT to watch.
        This gate decides WHEN the PAPER entry is allowed.

        A pullback touching its zone is never sufficient by itself.
        """
        symbol=str(row.get("symbol") or "").upper()
        episode=int(row.get("ready_episode") or 0)

        research=self._research_snapshot(symbol)
        raw=((research.get("raw") or {}).get("production_result") or {})
        tech=raw.get("technical") or research.get("technical") or {}
        trade=research.get("trade_plan") or {}
        pullback=trade.get("pullback") or {}

        trend=str(tech.get("trend_signal") or "unknown").lower()
        momentum=str(tech.get("momentum_signal") or "unknown").lower()

        ema9=_f(tech.get("ema_9"))
        rsi=_f(tech.get("rsi_14"))
        macd_hist=_f(tech.get("macd_histogram"))
        relvol=_f(tech.get("relative_volume"))

        stop=_f(
            proposal.get("invalidation")
            or proposal.get("stop")
            or proposal.get("stop_price")
            or row.get("invalidation")
        )

        entry_ref=_f(
            proposal.get("entry_price")
            or row.get("entry")
            or px
        )

        risk_per_share=_f(proposal.get("risk_per_share"))
        if risk_per_share is None and entry_ref and stop and entry_ref>stop:
            risk_per_share=entry_ref-stop

        entry_low=_f(pullback.get("entry_low"))
        entry_high=_f(pullback.get("entry_high"))

        hard_block=None

        if trend=="strong_bearish":
            hard_block="STRONG_BEARISH_TREND"
        elif momentum=="bearish":
            hard_block="BEARISH_MOMENTUM"
        elif stop is None or stop<=0 or px<=stop:
            hard_block="PRICE_AT_OR_BELOW_INVALIDATION"
        elif risk_per_share is None or risk_per_share<=0:
            hard_block="INVALID_ENTRY_RISK"
        elif entry_low is not None and px<entry_low:
            hard_block="PRICE_BELOW_PULLBACK_ZONE"
        elif entry_high is not None and px>entry_high:
            hard_block="PRICE_ABOVE_PULLBACK_ZONE"

        now=_now()

        with self._db() as db:
            old=db.execute("""
                SELECT *
                FROM v1517_entry_confirmation
                WHERE symbol=? AND ready_episode=?
            """,(symbol,episode)).fetchone()

            old=dict(old) if old else None

            if old:
                armed_at=old["armed_at"]
                first_price=_f(old.get("first_price")) or px
                low=min(_f(old.get("low_price")) or px,px)
                high=max(_f(old.get("high_price")) or px,px)
                previous=_f(old.get("last_price"))

                observations=int(old.get("observations") or 0)+1
                improving=int(old.get("improving_count") or 0)

                if previous:
                    if px > previous*1.0005:
                        improving += 1
                    elif px < previous*0.9995:
                        improving = 0
            else:
                armed_at=now
                first_price=px
                low=px
                high=px
                previous=None
                observations=1
                improving=0

            try:
                armed_dt=datetime.fromisoformat(armed_at)
                elapsed=max(
                    0.0,
                    (
                        datetime.now(timezone.utc)
                        - armed_dt.astimezone(timezone.utc)
                    ).total_seconds()
                )
            except Exception:
                elapsed=0.0

            rebound_r=(
                (px-low)/risk_per_share
                if risk_per_share and risk_per_share>0
                else 0.0
            )

            # ---------------- QUALITY SCORE ----------------
            score=0.0

            # Trend: max 20
            if trend=="strong_bullish":
                score += 20
            elif trend=="bullish":
                score += 17
            elif trend=="neutral":
                score += 10
            else:
                score += 4

            # Momentum: max 15
            if momentum=="bullish":
                score += 15
            elif momentum=="neutral":
                score += 8
            else:
                score += 3

            # EMA reclaim: max 10
            if ema9 is not None and px>=ema9:
                score += 10

            # MACD: max 10
            if macd_hist is not None and macd_hist>0:
                score += 10

            # RSI: max 10
            if rsi is not None:
                if 45 <= rsi <= 70:
                    score += 10
                elif 40 <= rsi <= 75:
                    score += 5

            # Relative volume: max 10
            if relvol is not None:
                if relvol>=1.0:
                    score += 10
                elif relvol>=0.8:
                    score += 6
                elif relvol>=0.6:
                    score += 3

            # Actual live rebound: max 20
            if rebound_r>=0.20:
                score += 20
            elif rebound_r>=0.12:
                score += 15
            elif rebound_r>=0.08:
                score += 8

            # Persistent quote improvement: max 5
            if improving>=2:
                score += 5

            if hard_block:
                state="BLOCKED"
                block_reason=hard_block
                confirmed=False
            else:
                enough_time=elapsed>=self.entry_min_seconds
                enough_obs=observations>=self.entry_min_observations
                actual_rebound=rebound_r>=self.entry_min_rebound_r
                persistent=improving>=2
                enough_score=score>=self.entry_min_score

                confirmed=all((
                    enough_time,
                    enough_obs,
                    actual_rebound,
                    persistent,
                    enough_score,
                ))

                if confirmed:
                    state="CONFIRMED"
                    block_reason=None
                else:
                    state="ARMED"

                    missing=[]
                    if not enough_time:
                        missing.append("OBSERVATION_TIME")
                    if not enough_obs:
                        missing.append("OBSERVATION_COUNT")
                    if not actual_rebound:
                        missing.append("LIVE_REBOUND")
                    if not persistent:
                        missing.append("PERSISTENCE")
                    if not enough_score:
                        missing.append("QUALITY_SCORE")

                    block_reason="WAITING_FOR_"+",".join(missing)

            diagnostics={
                "strategy_version":"ENTRY_V2",
                "trend":trend,
                "momentum":momentum,
                "ema9":ema9,
                "rsi14":rsi,
                "macd_histogram":macd_hist,
                "relative_volume":relvol,
                "entry_low":entry_low,
                "entry_high":entry_high,
                "stop":stop,
                "risk_per_share":risk_per_share,
                "elapsed_seconds":round(elapsed,2),
                "observations":observations,
                "improving_count":improving,
                "rebound_r":round(rebound_r,4),
                "entry_quality_score":round(score,2),
                "minimum_score":self.entry_min_score,
            }

            db.execute("""
                INSERT INTO v1517_entry_confirmation(
                    symbol,ready_episode,strategy_version,state,armed_at,
                    first_price,low_price,high_price,last_price,
                    observations,improving_count,rebound_r,
                    entry_quality_score,block_reason,
                    diagnostics_json,updated_at
                )
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(symbol,ready_episode) DO UPDATE SET
                    state=excluded.state,
                    low_price=excluded.low_price,
                    high_price=excluded.high_price,
                    last_price=excluded.last_price,
                    observations=excluded.observations,
                    improving_count=excluded.improving_count,
                    rebound_r=excluded.rebound_r,
                    entry_quality_score=excluded.entry_quality_score,
                    block_reason=excluded.block_reason,
                    diagnostics_json=excluded.diagnostics_json,
                    updated_at=excluded.updated_at
            """,(
                symbol,episode,"ENTRY_V2",state,armed_at,
                first_price,low,high,px,
                observations,improving,rebound_r,
                score,block_reason,
                json.dumps(diagnostics,separators=(",",":")),
                now,
            ))

            db.commit()

        return {
            "confirmed":confirmed,
            "state":state,
            "score":round(score,2),
            "reason":block_reason,
            "diagnostics":diagnostics,
        }

    def _ensure_exit_engine_tables(self):
        with sqlite3.connect(self.db_path) as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS v1518_exit_state(
                    symbol TEXT NOT NULL,
                    ready_episode INTEGER NOT NULL,
                    strategy_version TEXT NOT NULL DEFAULT 'EXIT_V2',

                    original_quantity REAL,
                    remaining_quantity REAL,

                    initial_stop REAL,
                    protected_stop REAL,

                    highest_r REAL NOT NULL DEFAULT 0.0,

                    t1_order_id TEXT,
                    t1_requested_qty REAL,
                    t1_filled_qty REAL NOT NULL DEFAULT 0.0,

                    final_order_id TEXT,
                    final_reason TEXT,

                    state TEXT NOT NULL DEFAULT 'TRACKING',
                    last_broker_qty REAL,
                    last_error TEXT,

                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,

                    PRIMARY KEY(symbol,ready_episode)
                )
            """)

            db.execute("""
                CREATE INDEX IF NOT EXISTS idx_v1518_exit_state
                ON v1518_exit_state(state,updated_at)
            """)

            db.commit()

    def _exit_state(self,symbol,episode):
        with self._db() as db:
            row=db.execute("""
                SELECT *
                FROM v1518_exit_state
                WHERE symbol=? AND ready_episode=?
            """,(symbol.upper(),int(episode))).fetchone()

        return dict(row) if row else None

    def _ensure_exit_state(self,row,broker_qty=None):
        symbol=str(row.get("symbol") or "").upper()
        episode=int(row.get("ready_episode") or 0)

        existing=self._exit_state(symbol,episode)
        if existing:
            return existing

        tracked_qty=_f(row.get("quantity"))
        original_qty=tracked_qty

        remaining_qty=(
            broker_qty
            if broker_qty is not None
            else tracked_qty
        )

        initial_stop=_f(row.get("invalidation"))
        now=_now()

        with self._db() as db:
            db.execute("""
                INSERT OR IGNORE INTO v1518_exit_state(
                    symbol,
                    ready_episode,
                    strategy_version,
                    original_quantity,
                    remaining_quantity,
                    initial_stop,
                    protected_stop,
                    highest_r,
                    state,
                    last_broker_qty,
                    created_at,
                    updated_at
                )
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
            """,(
                symbol,
                episode,
                "EXIT_V2",
                original_qty,
                remaining_qty,
                initial_stop,
                None,
                0.0,
                "TRACKING",
                broker_qty,
                now,
                now,
            ))

            db.commit()

        return self._exit_state(symbol,episode)

    def _broker_orders(self):
        if not self.order_getter:
            return None

        try:
            rows=self.order_getter(200) or []
        except TypeError:
            try:
                rows=self.order_getter() or []
            except Exception:
                return None
        except Exception:
            return None

        if not isinstance(rows,list):
            return None

        return [
            r for r in rows
            if isinstance(r,dict)
        ]

    def _reconcile_exit_state(self,row,broker_qty=None):
        """
        Reconcile V15.18 exit orders from Alpaca PAPER.

        Important:
        - Never infer an exit fill from submission alone.
        - Never overwrite the original entry alpaca_order_id.
        - Unknown broker/order state fails closed.
        """
        symbol=str(row.get("symbol") or "").upper()
        episode=int(row.get("ready_episode") or 0)

        st=self._ensure_exit_state(row,broker_qty)
        if not st:
            return None

        orders=self._broker_orders()

        if orders is None:
            with self._db() as db:
                db.execute("""
                    UPDATE v1518_exit_state
                    SET last_error=?,
                        last_broker_qty=?,
                        updated_at=?
                    WHERE symbol=? AND ready_episode=?
                """,(
                    "BROKER_ORDER_STATE_UNKNOWN",
                    broker_qty,
                    _now(),
                    symbol,
                    episode,
                ))
                db.commit()

            return self._exit_state(symbol,episode)

        byid={
            str(o.get("id")):o
            for o in orders
            if o.get("id")
        }

        t1_filled=_f(st.get("t1_filled_qty")) or 0.0
        state=str(st.get("state") or "TRACKING")
        last_error=None

        t1_id=str(st.get("t1_order_id") or "")
        if t1_id:
            o=byid.get(t1_id)

            if o:
                filled=_f(o.get("filled_qty"))
                if filled is not None:
                    t1_filled=max(t1_filled,filled)

                status=str(o.get("status") or "").upper()

                if status=="FILLED":
                    state="T1_PARTIAL_FILLED"
                elif status=="PARTIALLY_FILLED":
                    state="T1_PARTIAL_FILLING"
                elif status in {
                    "CANCELED",
                    "CANCELLED",
                    "EXPIRED",
                    "REJECTED",
                }:
                    state="T1_PARTIAL_FAILED"
                    last_error=f"T1_ORDER_{status}"

        final_id=str(st.get("final_order_id") or "")
        if final_id:
            o=byid.get(final_id)

            if o:
                status=str(o.get("status") or "").upper()

                if status=="FILLED":
                    state="CLOSED"
                elif status=="PARTIALLY_FILLED":
                    state="FINAL_EXIT_FILLING"
                elif status in {
                    "CANCELED",
                    "CANCELLED",
                    "EXPIRED",
                    "REJECTED",
                }:
                    state="FINAL_EXIT_FAILED"
                    last_error=f"FINAL_ORDER_{status}"

        with self._db() as db:
            db.execute("""
                UPDATE v1518_exit_state
                SET t1_filled_qty=?,
                    remaining_quantity=?,
                    last_broker_qty=?,
                    state=?,
                    last_error=?,
                    updated_at=?
                WHERE symbol=? AND ready_episode=?
            """,(
                t1_filled,
                broker_qty,
                broker_qty,
                state,
                last_error,
                _now(),
                symbol,
                episode,
            ))

            db.commit()

        return self._exit_state(symbol,episode)

    def _db(self):
        db=sqlite3.connect(self.db_path)
        db.row_factory=sqlite3.Row
        return db

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        self.thread=threading.Thread(target=self._loop,daemon=True,name="baby-v1515-autopilot")
        self.thread.start()

    def stop(self):
        self.stop_event.set()

    def _log(self,symbol,episode,action,reason,payload=None):
        try:
            with self._db() as db:
                db.execute("""INSERT INTO v1515_actions(symbol,episode_key,action,reason,payload_json,created_at)
                              VALUES(?,?,?,?,?,?)""",
                           (symbol,str(episode),action,reason,json.dumps(payload or {},default=str),_now()))
                db.commit()
        except Exception:
            pass

    def _notify(self,title,message,symbol=None,episode=None):
        # V15.16: authenticated self-hosted ntfy + signed Baby Quick link.
        # Notification links identify a setup only; they never authorize execution.
        try:
            from .v1516_ntfy import secure_ntfy
            secure_ntfy.publish(
                title=title,
                message=message,
                symbol=symbol,
                episode=episode,
            )
        except Exception:
            pass

        # Retain Baby's internal notification/event channel.
        try:
            if self.notifier:
                self.notifier.emit(
                    dedupe_key=f"v1515:{title}:{symbol}:{episode}:{hash(message)}",
                    title=title,message=message,severity="IMPORTANT",
                    symbol=symbol,force=True
                )
        except Exception:
            pass

    @staticmethod
    def _equity(account):
        if not isinstance(account,dict): return None
        for k in ("equity","portfolio_value","account_equity"):
            v=_f(account.get(k))
            if v and v>0:return v
        return None

    @staticmethod
    def _price(q):
        if not isinstance(q,dict): return None
        for k in ("price","last","last_price","mid","quote_price"):
            v=_f(q.get(k))
            if v and v>0:return v
        bid=_f(q.get("bid_price") or q.get("bid"))
        ask=_f(q.get("ask_price") or q.get("ask"))
        if bid and ask:return (bid+ask)/2
        return ask or bid

    def _trades_today(self):
        today=datetime.now(timezone.utc).date().isoformat()
        with self._db() as db:
            row=db.execute("SELECT new_entries FROM v1515_daily_guard WHERE trade_date=?",(today,)).fetchone()
            return int(row["new_entries"]) if row else 0

    def _increment_today(self,equity):
        today=datetime.now(timezone.utc).date().isoformat()
        with self._db() as db:
            db.execute("""INSERT INTO v1515_daily_guard(trade_date,new_entries,starting_equity,last_updated_at)
                          VALUES(?,1,?,?)
                          ON CONFLICT(trade_date) DO UPDATE SET
                            new_entries=new_entries+1,last_updated_at=excluded.last_updated_at""",
                       (today,equity,_now()))
            db.commit()

    def _candidate_rows(self):
        # V15.15 hotfix: historical validation rows are evidence only.
        max_age_seconds=max(
            30,
            int(os.getenv("BABY_PAPER_ENTRY_MAX_AGE_SECONDS","180"))
        )
        cutoff=(datetime.now(timezone.utc)-timedelta(seconds=max_age_seconds)).isoformat()

        with self._db() as db:
            rows=db.execute("""
              SELECT fv.*
              FROM v1511_forward_validation fv
              JOIN v1511_readiness r
                ON r.symbol=fv.symbol
               AND r.state='SETUP_READY'
              JOIN candidate_alert_state c
                ON c.symbol=fv.symbol
               AND c.last_ready=1
               AND c.ready_episode=fv.ready_episode
              WHERE fv.alpaca_order_id IS NULL
                AND fv.paper_outcome IN ('NOT_EXECUTED','UNFILLED')
                AND fv.t0 >= ?
                AND fv.id=(
                    SELECT MAX(x.id)
                    FROM v1511_forward_validation x
                    WHERE x.symbol=fv.symbol
                )
              ORDER BY fv.t0 ASC
              LIMIT 25
            """,(cutoff,)).fetchall()
            return [dict(r) for r in rows]

    def _open_paper_rows(self):
        """
        Broker-management candidates.

        V15.18 intentionally does NOT filter by paper_outcome.

        paper_outcome describes the observed price path, not whether Alpaca
        still holds shares.

        Only ENTRY_V2-confirmed episodes are autonomously managed so legacy
        PAPER holdings cannot suddenly be sold by the new exit engine.
        """
        with self._db() as db:
            rows=db.execute("""
                SELECT fv.*
                FROM v1511_forward_validation fv
                WHERE fv.filled=1
                  AND fv.quantity IS NOT NULL
                  AND fv.quantity>0
                  AND EXISTS(
                      SELECT 1
                      FROM v1517_entry_confirmation ec
                      WHERE ec.symbol=fv.symbol
                        AND ec.ready_episode=fv.ready_episode
                        AND ec.strategy_version='ENTRY_V2'
                        AND ec.state='CONFIRMED'
                  )
                ORDER BY fv.id ASC
            """).fetchall()

            return [dict(r) for r in rows]

    def _already_actioned(self,symbol,episode,action):
        with self._db() as db:
            r=db.execute("""SELECT 1 FROM v1515_actions
                            WHERE symbol=? AND episode_key=? AND action=? LIMIT 1""",
                         (symbol,str(episode),action)).fetchone()
            return bool(r)

    def _size(self,equity,price,stop,setup_max_position_pct=None):
        allocation_pct=self.max_alloc

        try:
            if setup_max_position_pct is not None:
                setup_pct=float(setup_max_position_pct)/100.0
                if setup_pct>0:
                    allocation_pct=min(allocation_pct,setup_pct)
        except Exception:
            pass

        qty_alloc=int((equity*allocation_pct)//price)
        qty=qty_alloc

        if stop and stop>0 and stop<price:
            per_share=price-stop
            qty_risk=int((equity*self.max_risk)//per_share) if per_share>0 else qty_alloc
            qty=min(qty,qty_risk)

        return max(0,qty)

    def _has_open_symbol_position(self,symbol):
        try:
            with self._db() as db:
                row=db.execute(
                    """
                    SELECT 1
                    FROM v1511_forward_validation
                    WHERE symbol=?
                      AND filled=1
                      AND quantity>0
                      AND paper_outcome='OPEN'
                    LIMIT 1
                    """,
                    (symbol.upper(),)
                ).fetchone()
                return bool(row)
        except Exception:
            return None

    def _enter_once(self,row):
        symbol=row["symbol"]; episode=int(row["ready_episode"])
        if self._already_actioned(symbol,episode,"ENTRY_SUBMITTED"):
            return

        open_position_state=self._has_open_symbol_position(symbol)

        if open_position_state is None:
            if not self._already_actioned(symbol,episode,"ENTRY_BLOCKED_POSITION_STATE_UNKNOWN"):
                self._log(
                    symbol,
                    episode,
                    "ENTRY_BLOCKED_POSITION_STATE_UNKNOWN",
                    "LOCAL_POSITION_STATE_LOOKUP_FAILED",
                )
            return

        if open_position_state:
            if not self._already_actioned(symbol,episode,"ENTRY_SKIPPED_ALREADY_OPEN"):
                self._log(
                    symbol,
                    episode,
                    "ENTRY_SKIPPED_ALREADY_OPEN",
                    "SYMBOL_ALREADY_HAS_OPEN_PAPER_POSITION",
                )
                self._notify(
                    f"BABY — {symbol} setup tracked, position already open",
                    f"{symbol} has another current SETUP_READY episode, "
                    f"but Baby already holds an OPEN PAPER position in this symbol. "
                    f"No additional PAPER BUY submitted. "
                    f"The setup will continue to be tracked. "
                    f"Real-money execution DISABLED.",
                    symbol,
                    episode,
                )
            return
        if self._trades_today()>=self.max_trades:
            # V15.16: research/forward-validation continues after 3 trades.
            # Notify only once for this episode; never auto-enter it.
            if not self._already_actioned(symbol,episode,"ENTRY_SKIPPED_DAILY_LIMIT"):
                self._log(
                    symbol,episode,
                    "ENTRY_SKIPPED_DAILY_LIMIT",
                    "DAILY_TRADE_LIMIT_REACHED"
                )
                self._notify(
                    f"BABY — {symbol} SETUP_READY — daily limit reached",
                    f"{symbol} remains SETUP_READY and will continue to be tracked, "
                    f"but Baby has already used {self.max_trades}/{self.max_trades} "
                    f"PAPER entries today. No PAPER BUY submitted. "
                    f"Real-money execution DISABLED.",
                    symbol,
                    episode,
                )
            return

        proposal=self.proposal_getter(symbol)
        if not (proposal.get("eligible") and str(proposal.get("status") or "").upper()=="ELIGIBLE"):
            if not self._already_actioned(symbol,episode,"ENTRY_BLOCKED_NOT_ELIGIBLE"):
                self._log(symbol,episode,"ENTRY_BLOCKED_NOT_ELIGIBLE","SETUP_NO_LONGER_ELIGIBLE",proposal)
            return

        failed_structure=self._failed_setup_lock(row)
        if failed_structure:
            if not self._already_actioned(symbol,episode,"ENTRY_BLOCKED_FAILED_STRUCTURE"):
                self._log(
                    symbol,
                    episode,
                    "ENTRY_BLOCKED_FAILED_STRUCTURE",
                    failed_structure.get("reason") or "RECENT_FAILED_STRUCTURE_MATCH",
                    failed_structure,
                )
            return

        quote=self.quote_getter(symbol)
        px=self._price(quote)
        if not px:
            self._log(symbol,episode,"ENTRY_BLOCKED","NO_FRESH_QUOTE",quote)
            return

        confirmation=self._entry_confirmation(row,proposal,px)

        if not confirmation.get("confirmed"):
            if confirmation.get("state")=="BLOCKED":
                if not self._already_actioned(symbol,episode,"ENTRY_BLOCKED_QUALITY"):
                    self._log(
                        symbol,
                        episode,
                        "ENTRY_BLOCKED_QUALITY",
                        confirmation.get("reason") or "ENTRY_QUALITY_BLOCK",
                        confirmation,
                    )
            elif not self._already_actioned(symbol,episode,"ENTRY_ARMED"):
                self._log(
                    symbol,
                    episode,
                    "ENTRY_ARMED",
                    "WAITING_FOR_LIVE_ENTRY_CONFIRMATION",
                    confirmation,
                )
            return

        if not self._already_actioned(symbol,episode,"ENTRY_CONFIRMED_V2"):
            self._log(
                symbol,
                episode,
                "ENTRY_CONFIRMED_V2",
                "LIVE_REVERSAL_AND_QUALITY_GATE_PASSED",
                confirmation,
            )

        account=self.account_getter()
        equity=self._equity(account)
        if not equity:
            self._log(symbol,episode,"ENTRY_BLOCKED","NO_ACCOUNT_EQUITY",account)
            return

        stop=_f(
            proposal.get("invalidation")
            or proposal.get("stop")
            or proposal.get("stop_price")
            or row.get("invalidation")
        )
        qty=self._size(
            equity,
            px,
            stop,
            proposal.get("max_position_percent"),
        )
        if qty<=0:
            self._log(symbol,episode,"ENTRY_BLOCKED","POSITION_SIZE_ZERO",
                      {"equity":equity,"price":px,"stop":stop})
            return

        # Atomic local claim before broker call.
        self._log(symbol,episode,"ENTRY_CLAIMED","AUTOPILOT",
                  {"qty":qty,"price":px,"equity":equity})
        try:
            order=self.order_submitter(
                symbol=symbol, side="BUY", quantity=qty,
                order_type="MARKET", confirmation=PAPER_CONFIRMATION,
                client_order_id=f"baby-v1515-{symbol.lower()}-{episode}"
            )
        except Exception as exc:
            self._log(symbol,episode,"ENTRY_SUBMIT_UNKNOWN","BROKER_EXCEPTION",{"error":str(exc)})
            return

        oid=order.get("id") or order.get("order_id")
        if not oid:
            self._log(symbol,episode,"ENTRY_SUBMIT_UNKNOWN","BROKER_NO_ORDER_ID",order)
            return

        self.ledger.attach_order(symbol,episode,order,qty)
        self._increment_today(equity)
        self._log(symbol,episode,"ENTRY_SUBMITTED","ALPACA_PAPER",order)
        self._notify(
            f"BABY — {symbol} PAPER entry submitted",
            f"{qty} shares submitted to Alpaca PAPER. Episode {episode}. "
            f"Approx quote ${px:.2f}. Real-money execution DISABLED.",
            symbol,
            episode
        )

    def _exit_reconciliation_guard(self,row,broker_qty):
        """
        Exit V2 ownership guard.

        Autonomous SELL is permitted only when:
        - broker position state is known
        - exactly one live Baby PAPER episode claims the symbol
        - this row is that episode
        - tracked quantity matches broker quantity

        Everything ambiguous fails closed.
        """
        symbol=str(row.get("symbol") or "").upper()
        episode=int(row.get("ready_episode") or 0)

        if broker_qty is None:
            return {
                "eligible":False,
                "reason":"BROKER_POSITION_UNKNOWN",
            }

        try:
            with self._db() as db:
                rows=db.execute("""
                    SELECT
                        ready_episode,
                        quantity,
                        paper_outcome
                    FROM v1511_forward_validation fv
                    WHERE fv.symbol=?
                      AND fv.filled=1
                      AND fv.quantity>0
                      AND EXISTS(
                          SELECT 1
                          FROM v1517_entry_confirmation ec
                          WHERE ec.symbol=fv.symbol
                            AND ec.ready_episode=fv.ready_episode
                            AND ec.strategy_version='ENTRY_V2'
                            AND ec.state='CONFIRMED'
                      )
                    ORDER BY fv.id
                """,(symbol,)).fetchall()
        except Exception as exc:
            return {
                "eligible":False,
                "reason":"LEDGER_OWNERSHIP_LOOKUP_FAILED",
                "error":str(exc),
            }

        rows=[dict(r) for r in rows]

        if not rows:
            return {
                "eligible":False,
                "reason":"BROKER_POSITION_LEDGER_CLOSED"
                if broker_qty>0
                else "NO_LIVE_TRACKED_EPISODE",
                "broker_qty":broker_qty,
            }

        if len(rows)!=1:
            return {
                "eligible":False,
                "reason":"MULTIPLE_LIVE_EPISODES",
                "episodes":[r.get("ready_episode") for r in rows],
                "tracked_total":sum(float(r.get("quantity") or 0) for r in rows),
                "broker_qty":broker_qty,
            }

        owner=rows[0]

        if int(owner.get("ready_episode") or 0)!=episode:
            return {
                "eligible":False,
                "reason":"EPISODE_NOT_UNIQUE_OWNER",
                "owner_episode":owner.get("ready_episode"),
                "broker_qty":broker_qty,
            }

        tracked_qty=_f(owner.get("quantity"))

        if tracked_qty is None:
            return {
                "eligible":False,
                "reason":"TRACKED_QUANTITY_UNKNOWN",
            }

        # Before Exit V2 has managed the trade, the forward-validation
        # quantity is the expected broker quantity.
        #
        # After a partial exit has actually been reconciled, the broker
        # quantity will legitimately be smaller. In that case the persisted
        # Exit V2 remaining_quantity becomes the expected quantity.
        exit_state=self._exit_state(symbol,episode)

        expected_qty=tracked_qty
        quantity_source="FORWARD_VALIDATION"

        if exit_state:
            remaining=_f(exit_state.get("remaining_quantity"))
            t1_filled=_f(exit_state.get("t1_filled_qty")) or 0.0

            if remaining is not None and t1_filled>0:
                expected_qty=remaining
                quantity_source="EXIT_V2_REMAINING"

        tolerance=max(
            0.0001,
            abs(expected_qty)*0.001,
        )

        if abs(float(broker_qty)-expected_qty)>tolerance:
            return {
                "eligible":False,
                "reason":"BROKER_LEDGER_QUANTITY_MISMATCH",
                "tracked_qty":tracked_qty,
                "expected_qty":expected_qty,
                "quantity_source":quantity_source,
                "broker_qty":broker_qty,
            }

        return {
            "eligible":True,
            "reason":"UNIQUE_EPISODE_BROKER_MATCH",
            "episode":episode,
            "tracked_qty":tracked_qty,
            "expected_qty":expected_qty,
            "quantity_source":quantity_source,
            "broker_qty":broker_qty,
        }

    def _broker_position_qty(self, symbol):
        """
        Return actual Alpaca PAPER quantity held for symbol.

        Fail closed:
        - None means broker position state could not be confirmed.
        - 0.0 means broker confirmed no long position exists.
        """
        if not self.position_getter:
            return None

        try:
            positions = self.position_getter()
        except Exception:
            return None

        if not isinstance(positions, list):
            return None

        symbol = str(symbol or "").upper()

        for position in positions:
            if not isinstance(position, dict):
                continue

            if str(position.get("symbol", "")).upper() != symbol:
                continue

            qty = _f(position.get("qty"))
            if qty is None:
                return None

            return max(0.0, qty)

        return 0.0

    def _submit_exit_v2(self,row,qty,reason,kind):
        """
        Submit one idempotent Alpaca PAPER SELL.

        kind:
          T1    -> partial profit
          FINAL -> T2 / protected stop / original stop

        Claim is persisted BEFORE broker submission.

        If broker submission becomes unknown, Baby fails closed and will not
        automatically retry that exit because duplicate SELLs are worse than
        delayed manual reconciliation.
        """
        symbol=str(row.get("symbol") or "").upper()
        episode=int(row.get("ready_episode") or 0)

        qty=_f(qty)
        if qty is None or qty<=0:
            return {
                "submitted":False,
                "reason":"INVALID_EXIT_QUANTITY",
            }

        st=self._exit_state(symbol,episode)
        if not st:
            return {
                "submitted":False,
                "reason":"EXIT_STATE_MISSING",
            }

        if kind=="T1":
            if st.get("t1_order_id"):
                return {
                    "submitted":False,
                    "reason":"T1_ORDER_ALREADY_EXISTS",
                }

            if str(st.get("state") or "") in {
                "T1_PARTIAL_CLAIMED",
                "T1_PARTIAL_SUBMIT_UNKNOWN",
                "T1_PARTIAL_SUBMITTED",
                "T1_PARTIAL_FILLING",
            }:
                return {
                    "submitted":False,
                    "reason":"T1_ORDER_ALREADY_CLAIMED",
                }

            claim_state="T1_PARTIAL_CLAIMED"
            client_order_id=(
                f"baby-v1518-t1-{symbol.lower()}-{episode}"
            )

            with self._db() as db:
                db.execute("""
                    UPDATE v1518_exit_state
                    SET state=?,
                        t1_requested_qty=?,
                        updated_at=?
                    WHERE symbol=?
                      AND ready_episode=?
                """,(
                    claim_state,
                    qty,
                    _now(),
                    symbol,
                    episode,
                ))
                db.commit()

        else:
            if st.get("final_order_id"):
                return {
                    "submitted":False,
                    "reason":"FINAL_ORDER_ALREADY_EXISTS",
                }

            if str(st.get("state") or "") in {
                "FINAL_EXIT_CLAIMED",
                "FINAL_EXIT_SUBMIT_UNKNOWN",
                "FINAL_EXIT_SUBMITTED",
                "FINAL_EXIT_FILLING",
            }:
                return {
                    "submitted":False,
                    "reason":"FINAL_ORDER_ALREADY_CLAIMED",
                }

            claim_state="FINAL_EXIT_CLAIMED"

            safe_reason=(
                str(reason or "exit")
                .lower()
                .replace("_","-")
            )

            client_order_id=(
                f"baby-v1518-{safe_reason}-"
                f"{symbol.lower()}-{episode}"
            )[:48]

            with self._db() as db:
                db.execute("""
                    UPDATE v1518_exit_state
                    SET state=?,
                        final_reason=?,
                        updated_at=?
                    WHERE symbol=?
                      AND ready_episode=?
                """,(
                    claim_state,
                    reason,
                    _now(),
                    symbol,
                    episode,
                ))
                db.commit()

        self._log(
            symbol,
            episode,
            f"EXIT_V2_{kind}_CLAIMED",
            reason,
            {
                "quantity":qty,
                "client_order_id":client_order_id,
            },
        )

        try:
            order=self.order_submitter(
                symbol=symbol,
                side="SELL",
                quantity=qty,
                order_type="MARKET",
                confirmation=PAPER_CONFIRMATION,
                client_order_id=client_order_id,
            )
        except Exception as exc:
            unknown_state=(
                "T1_PARTIAL_SUBMIT_UNKNOWN"
                if kind=="T1"
                else "FINAL_EXIT_SUBMIT_UNKNOWN"
            )

            with self._db() as db:
                db.execute("""
                    UPDATE v1518_exit_state
                    SET state=?,
                        last_error=?,
                        updated_at=?
                    WHERE symbol=?
                      AND ready_episode=?
                """,(
                    unknown_state,
                    str(exc),
                    _now(),
                    symbol,
                    episode,
                ))
                db.commit()

            self._log(
                symbol,
                episode,
                f"EXIT_V2_{kind}_SUBMIT_UNKNOWN",
                "BROKER_EXCEPTION",
                {"error":str(exc)},
            )

            return {
                "submitted":False,
                "reason":"BROKER_SUBMIT_UNKNOWN",
            }

        oid=order.get("id") or order.get("order_id")

        if not oid:
            unknown_state=(
                "T1_PARTIAL_SUBMIT_UNKNOWN"
                if kind=="T1"
                else "FINAL_EXIT_SUBMIT_UNKNOWN"
            )

            with self._db() as db:
                db.execute("""
                    UPDATE v1518_exit_state
                    SET state=?,
                        last_error=?,
                        updated_at=?
                    WHERE symbol=?
                      AND ready_episode=?
                """,(
                    unknown_state,
                    "BROKER_NO_ORDER_ID",
                    _now(),
                    symbol,
                    episode,
                ))
                db.commit()

            return {
                "submitted":False,
                "reason":"BROKER_NO_ORDER_ID",
            }

        if kind=="T1":
            state="T1_PARTIAL_SUBMITTED"

            with self._db() as db:
                db.execute("""
                    UPDATE v1518_exit_state
                    SET t1_order_id=?,
                        state=?,
                        last_error=NULL,
                        updated_at=?
                    WHERE symbol=?
                      AND ready_episode=?
                """,(
                    str(oid),
                    state,
                    _now(),
                    symbol,
                    episode,
                ))
                db.commit()

        else:
            state="FINAL_EXIT_SUBMITTED"

            with self._db() as db:
                db.execute("""
                    UPDATE v1518_exit_state
                    SET final_order_id=?,
                        final_reason=?,
                        state=?,
                        last_error=NULL,
                        updated_at=?
                    WHERE symbol=?
                      AND ready_episode=?
                """,(
                    str(oid),
                    reason,
                    state,
                    _now(),
                    symbol,
                    episode,
                ))
                db.commit()

        self._log(
            symbol,
            episode,
            f"EXIT_V2_{kind}_SUBMITTED",
            reason,
            order,
        )

        self._notify(
            f"BABY — {symbol} PAPER exit submitted",
            f"SELL {qty:g} shares submitted to Alpaca PAPER. "
            f"Reason: {reason}. "
            f"Real-money execution DISABLED.",
            symbol,
            episode,
        )

        return {
            "submitted":True,
            "order":order,
        }


    def _exit_if_needed(self,row):
        """
        V15.18 PAPER Exit Engine V2.

        Broker position is the source of truth.

        Management:
          < +0.75R  -> original stop
          >=+0.75R  -> protection armed
          >=+1.00R  -> protected stop near breakeven
          T1        -> partial profit
          after T1  -> protect remainder at +0.10R by default
          T2        -> exit remainder

        PAPER ONLY.
        """
        symbol=str(row.get("symbol") or "").upper()
        episode=int(row.get("ready_episode") or 0)

        q=self.quote_getter(symbol)
        px=self._price(q)

        if not px:
            return

        fill=_f(row.get("fill_price") or row.get("entry"))
        stop=_f(row.get("invalidation"))
        t1=_f(row.get("target1"))
        t2=_f(row.get("target2"))

        if (
            fill is None
            or stop is None
            or fill<=0
            or stop<=0
            or fill<=stop
        ):
            self._log(
                symbol,
                episode,
                "EXIT_V2_BLOCKED",
                "INVALID_INITIAL_RISK_STRUCTURE",
                {
                    "fill":fill,
                    "stop":stop,
                },
            )
            return

        risk=fill-stop

        broker_qty=self._broker_position_qty(symbol)

        if broker_qty is None:
            if not self._already_actioned(
                symbol,
                episode,
                "EXIT_V2_BROKER_POSITION_UNKNOWN",
            ):
                self._log(
                    symbol,
                    episode,
                    "EXIT_V2_BROKER_POSITION_UNKNOWN",
                    "BROKER_POSITION_LOOKUP_FAILED",
                )
            return

        # Broker confirms position is already gone.
        # Do not submit another SELL.
        if broker_qty<=0:
            self._ensure_exit_state(row,broker_qty=0)

            with self._db() as db:
                db.execute("""
                    UPDATE v1518_exit_state
                    SET remaining_quantity=0,
                        last_broker_qty=0,
                        state='CLOSED_BROKER_ZERO',
                        updated_at=?
                    WHERE symbol=?
                      AND ready_episode=?
                """,(
                    _now(),
                    symbol,
                    episode,
                ))
                db.commit()

            return

        ownership=self._exit_reconciliation_guard(
            row,
            broker_qty,
        )

        if not ownership.get("eligible"):
            action=(
                "EXIT_V2_RECONCILIATION_BLOCKED_"
                + str(
                    ownership.get("reason")
                    or "UNKNOWN"
                )
            )

            if not self._already_actioned(
                symbol,
                episode,
                action,
            ):
                self._log(
                    symbol,
                    episode,
                    action,
                    ownership.get("reason")
                    or "EXIT_RECONCILIATION_REQUIRED",
                    ownership,
                )

            return

        st=self._reconcile_exit_state(
            row,
            broker_qty=broker_qty,
        )

        if not st:
            return

        state=str(st.get("state") or "TRACKING")

        # Never place another SELL while broker outcome of an existing
        # exit order is unresolved.
        if state in {
            "T1_PARTIAL_CLAIMED",
            "T1_PARTIAL_SUBMIT_UNKNOWN",
            "T1_PARTIAL_SUBMITTED",
            "T1_PARTIAL_FILLING",
            "FINAL_EXIT_CLAIMED",
            "FINAL_EXIT_SUBMIT_UNKNOWN",
            "FINAL_EXIT_SUBMITTED",
            "FINAL_EXIT_FILLING",
        }:
            return

        if state in {
            "CLOSED",
            "CLOSED_BROKER_ZERO",
        }:
            return

        r_now=(px-fill)/risk

        highest_r=max(
            _f(st.get("highest_r")) or 0.0,
            r_now,
        )

        protected_stop=_f(st.get("protected_stop"))

        new_state=state

        # --------------------------------------------------
        # +0.75R: protection is armed.
        # --------------------------------------------------
        if (
            highest_r>=self.exit_protect_arm_r
            and new_state=="TRACKING"
        ):
            new_state="PROTECTION_ARMED"

        # --------------------------------------------------
        # +1R: original full -1R loss is no longer allowed.
        #
        # Default protected stop = -0.05R from entry.
        # This leaves a small amount of execution noise.
        # --------------------------------------------------
        if highest_r>=self.exit_protect_r:
            candidate=(
                fill
                + self.exit_protected_stop_r*risk
            )

            if protected_stop is None:
                protected_stop=candidate
            else:
                protected_stop=max(
                    protected_stop,
                    candidate,
                )

            if new_state in {
                "TRACKING",
                "PROTECTION_ARMED",
            }:
                new_state="PROTECTED"

        t1_filled=_f(st.get("t1_filled_qty")) or 0.0

        # Once T1 partial profit has actually filled, protect some
        # positive R on the remainder.
        if t1_filled>0:
            post_t1_stop=(
                fill
                + self.exit_post_t1_stop_r*risk
            )

            if protected_stop is None:
                protected_stop=post_t1_stop
            else:
                protected_stop=max(
                    protected_stop,
                    post_t1_stop,
                )

            if new_state not in {
                "FINAL_EXIT_FAILED",
                "T1_PARTIAL_FAILED",
            }:
                new_state="T1_PARTIAL_FILLED"

        with self._db() as db:
            db.execute("""
                UPDATE v1518_exit_state
                SET highest_r=?,
                    protected_stop=?,
                    remaining_quantity=?,
                    last_broker_qty=?,
                    state=?,
                    updated_at=?
                WHERE symbol=?
                  AND ready_episode=?
            """,(
                highest_r,
                protected_stop,
                broker_qty,
                broker_qty,
                new_state,
                _now(),
                symbol,
                episode,
            ))
            db.commit()

        st=self._exit_state(symbol,episode)

        # ==================================================
        # EXIT PRIORITY
        #
        # 1. Original invalidation
        # 2. Protected stop
        # 3. T2
        # 4. T1 partial
        # ==================================================

        if px<=stop:
            self._submit_exit_v2(
                row,
                broker_qty,
                "ORIGINAL_INVALIDATION",
                "FINAL",
            )
            return

        if (
            protected_stop is not None
            and px<=protected_stop
        ):
            self._submit_exit_v2(
                row,
                broker_qty,
                "PROTECTED_STOP",
                "FINAL",
            )
            return

        if t2 is not None and px>=t2:
            self._submit_exit_v2(
                row,
                broker_qty,
                "T2_TARGET",
                "FINAL",
            )
            return

        # Partial T1 only if we have never submitted it.
        if (
            t1 is not None
            and px>=t1
            and not st.get("t1_order_id")
            and (_f(st.get("t1_filled_qty")) or 0)<=0
        ):
            raw_partial=(
                broker_qty
                * self.exit_t1_fraction
            )

            # Preserve whole-share behavior for whole-share positions.
            if abs(broker_qty-round(broker_qty))<1e-9:
                partial_qty=float(
                    max(
                        1,
                        int(raw_partial),
                    )
                )
            else:
                partial_qty=round(
                    raw_partial,
                    6,
                )

            partial_qty=min(
                partial_qty,
                broker_qty,
            )

            if partial_qty>0:
                self._submit_exit_v2(
                    row,
                    partial_qty,
                    "T1_PARTIAL",
                    "T1",
                )

    def _loop(self):
        while not self.stop_event.is_set():
            try:
                if self.enabled:
                    for row in self._candidate_rows():
                        self._enter_once(row)
                    for row in self._open_paper_rows():
                        self._exit_if_needed(row)
            except Exception as exc:
                self._log(None,0,"WORKER_ERROR","LOOP_EXCEPTION",{"error":str(exc)})
            self.stop_event.wait(self.interval)
