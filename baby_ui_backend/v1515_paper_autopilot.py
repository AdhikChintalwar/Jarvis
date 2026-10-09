from __future__ import annotations
import hashlib, json, os, sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

def now_iso():
    return datetime.now(timezone.utc).isoformat()

@dataclass
class PaperAutopilotConfig:
    enabled: bool = True
    max_allocation_pct: float = 0.20
    max_new_trades_per_day: int = 3
    max_portfolio_risk_pct: float = 0.01
    max_daily_loss_pct: float = 0.03
    severe_market_exit_enabled: bool = True

    @classmethod
    def from_env(cls):
        return cls(
            enabled=os.getenv("BABY_PAPER_AUTOPILOT_ENABLED","true").lower()=="true",
            max_allocation_pct=float(os.getenv("BABY_PAPER_MAX_ALLOCATION_PCT","0.20")),
            max_new_trades_per_day=int(os.getenv("BABY_PAPER_MAX_NEW_TRADES_PER_DAY","3")),
            max_portfolio_risk_pct=float(os.getenv("BABY_PAPER_MAX_PORTFOLIO_RISK_PCT","0.01")),
            max_daily_loss_pct=float(os.getenv("BABY_PAPER_MAX_DAILY_LOSS_PCT","0.03")),
            severe_market_exit_enabled=os.getenv("BABY_PAPER_SEVERE_MARKET_EXIT_ENABLED","true").lower()=="true",
        )

class PaperAutopilotStore:
    def __init__(self, db_path=None):
        self.db_path = Path(db_path or os.getenv("BABY_UI_DB") or os.getenv("BABY_UI_DB_PATH") or "data/baby_ui.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure()

    def _connect(self):
        db=sqlite3.connect(self.db_path)
        db.row_factory=sqlite3.Row
        return db

    def _ensure(self):
        with self._connect() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS v1515_setup_episodes(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              episode_key TEXT NOT NULL UNIQUE,
              symbol TEXT NOT NULL,
              setup_fingerprint TEXT NOT NULL,
              state TEXT NOT NULL,
              opened_at TEXT NOT NULL,
              last_seen_at TEXT NOT NULL,
              closed_at TEXT,
              email_sent_at TEXT,
              push_sent_at TEXT,
              forward_validation_id TEXT,
              paper_approval_id TEXT,
              paper_order_id TEXT,
              entry_price REAL,
              stop_price REAL,
              target1 REAL,
              target2 REAL,
              quantity REAL,
              allocation_value REAL,
              close_price REAL,
              close_reason TEXT,
              meta_json TEXT NOT NULL DEFAULT '{}'
            );
            CREATE INDEX IF NOT EXISTS idx_v1515_episode_symbol_state
              ON v1515_setup_episodes(symbol,state);
            CREATE TABLE IF NOT EXISTS v1515_daily_guard(
              trade_date TEXT PRIMARY KEY,
              new_entries INTEGER NOT NULL DEFAULT 0,
              realized_pnl REAL NOT NULL DEFAULT 0,
              starting_equity REAL,
              last_updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS v1515_actions(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              symbol TEXT,
              episode_key TEXT,
              action TEXT NOT NULL,
              reason TEXT NOT NULL,
              payload_json TEXT NOT NULL DEFAULT '{}',
              created_at TEXT NOT NULL
            );
            """)

    @staticmethod
    def fingerprint(symbol:str, setup:dict[str,Any]) -> str:
        stable={
          "symbol":symbol.upper(),
          "entry":setup.get("entry") or setup.get("entry_price"),
          "stop":setup.get("stop") or setup.get("stop_price"),
          "t1":setup.get("t1") or setup.get("target1"),
          "t2":setup.get("t2") or setup.get("target2"),
          "setup_type":setup.get("setup_type") or setup.get("setup_status"),
        }
        raw=json.dumps(stable,sort_keys=True,separators=(",",":"))
        return hashlib.sha256(raw.encode()).hexdigest()[:24]

    def get_open_episode(self,symbol):
        with self._connect() as db:
            r=db.execute("SELECT * FROM v1515_setup_episodes WHERE symbol=? AND state='OPEN' ORDER BY id DESC LIMIT 1",(symbol.upper(),)).fetchone()
            return dict(r) if r else None

    def open_or_touch(self,symbol,setup):
        symbol=symbol.upper()
        old=self.get_open_episode(symbol)
        now=now_iso()
        if old:
            with self._connect() as db:
                db.execute("UPDATE v1515_setup_episodes SET last_seen_at=? WHERE id=?",(now,old["id"]))
            old["last_seen_at"]=now
            return old,False
        fp=self.fingerprint(symbol,setup)
        key=f"{symbol}:{fp}:{now}"
        with self._connect() as db:
            cur=db.execute("""
            INSERT INTO v1515_setup_episodes
            (episode_key,symbol,setup_fingerprint,state,opened_at,last_seen_at,
             entry_price,stop_price,target1,target2,meta_json)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """,(key,symbol,fp,"OPEN",now,now,
                 setup.get("entry") or setup.get("entry_price"),
                 setup.get("stop") or setup.get("stop_price"),
                 setup.get("t1") or setup.get("target1"),
                 setup.get("t2") or setup.get("target2"),
                 json.dumps(setup,default=str)))
            row=db.execute("SELECT * FROM v1515_setup_episodes WHERE id=?",(cur.lastrowid,)).fetchone()
            return dict(row),True

    def close_episode(self,symbol,reason,close_price=None):
        ep=self.get_open_episode(symbol)
        if not ep: return None
        with self._connect() as db:
            db.execute("""UPDATE v1515_setup_episodes
                          SET state='CLOSED',closed_at=?,close_reason=?,close_price=?
                          WHERE id=?""",(now_iso(),reason,close_price,ep["id"]))
        return True

    def trades_today(self,trade_date):
        with self._connect() as db:
            r=db.execute("SELECT new_entries FROM v1515_daily_guard WHERE trade_date=?",(trade_date,)).fetchone()
            return int(r["new_entries"]) if r else 0

    def increment_trade_count(self,trade_date,starting_equity=None):
        with self._connect() as db:
            db.execute("""
            INSERT INTO v1515_daily_guard(trade_date,new_entries,starting_equity,last_updated_at)
            VALUES (?,1,?,?)
            ON CONFLICT(trade_date) DO UPDATE SET
              new_entries=new_entries+1,
              starting_equity=COALESCE(v1515_daily_guard.starting_equity,excluded.starting_equity),
              last_updated_at=excluded.last_updated_at
            """,(trade_date,starting_equity,now_iso()))

class PaperAutopilot:
    """PAPER ONLY. No real-money route or credentials."""
    def __init__(self,store=None,cfg=None):
        self.store=store or PaperAutopilotStore()
        self.cfg=cfg or PaperAutopilotConfig.from_env()

    def sizing(self,portfolio_equity,entry,stop):
        if portfolio_equity<=0 or entry<=0:
            return {"eligible":False,"reason":"INVALID_EQUITY_OR_ENTRY"}
        max_value=portfolio_equity*self.cfg.max_allocation_pct
        qty_alloc=int(max_value//entry)
        if qty_alloc<=0:
            return {"eligible":False,"reason":"ALLOCATION_TOO_SMALL"}
        qty=qty_alloc
        risk_budget=portfolio_equity*self.cfg.max_portfolio_risk_pct
        if stop and 0<stop<entry:
            rps=entry-stop
            qty=min(qty,int(risk_budget//rps))
        if qty<=0:
            return {"eligible":False,"reason":"RISK_BUDGET_TOO_SMALL"}
        return {"eligible":True,"quantity":qty,
                "allocation_value":round(qty*entry,2),
                "max_allocation_value":round(max_value,2),
                "risk_budget":round(risk_budget,2)}

    def can_enter(self,trade_date,portfolio_equity,quote_price,stop,entry_low=None,entry_high=None):
        if not self.cfg.enabled:
            return {"eligible":False,"reason":"PAPER_AUTOPILOT_DISABLED"}
        used=self.store.trades_today(trade_date)
        if used>=self.cfg.max_new_trades_per_day:
            return {"eligible":False,"reason":"DAILY_TRADE_LIMIT_REACHED","trades_today":used}
        if entry_low is not None and quote_price<entry_low:
            return {"eligible":False,"reason":"QUOTE_BELOW_ENTRY_ZONE"}
        if entry_high is not None and quote_price>entry_high:
            return {"eligible":False,"reason":"QUOTE_ABOVE_ENTRY_ZONE_NO_CHASE"}
        s=self.sizing(portfolio_equity,quote_price,stop)
        if not s["eligible"]: return s
        return {"eligible":True,"reason":"PAPER_ENTRY_ALLOWED","trades_today":used,**s}

    def market_risk_state(self,metrics):
        spy=float(metrics.get("spy_pct",0) or 0)
        qqq=float(metrics.get("qqq_pct",0) or 0)
        iwm=float(metrics.get("iwm_pct",0) or 0)
        breadth=float(metrics.get("breadth_pct",50) or 50)
        worst=min(spy,qqq,iwm)
        if worst<=-3.0 and breadth<=20:
            state,reason="SEVERE_RISK_OFF","BROAD_MARKET_SEVERE_DOWNSIDE"
        elif worst<=-2.0 and breadth<=30:
            state,reason="RISK_OFF","BROAD_MARKET_DOWNSIDE"
        elif worst<=-1.0 or breadth<=40:
            state,reason="CAUTION","MARKET_WEAKNESS"
        else:
            state,reason="NORMAL","NO_BROAD_MARKET_STRESS"
        return {"state":state,"reason":reason,"metrics":metrics,"real_money_execution":"DISABLED"}

    def sudden_drop(self,entry_price,current_price,short_window_pct=0.0,volume_ratio=1.0):
        if entry_price<=0 or current_price<=0:
            return {"trigger":False,"reason":"INVALID_PRICE"}
        from_entry=(current_price/entry_price-1)*100
        trigger=(from_entry<=-5.0 or short_window_pct<=-3.0 or
                 (short_window_pct<=-2.0 and volume_ratio>=2.0))
        return {"trigger":trigger,
                "reason":"RAPID_DOWNSIDE_MOVE" if trigger else "NO_EMERGENCY_DROP",
                "from_entry_pct":round(from_entry,3),
                "short_window_pct":short_window_pct,
                "volume_ratio":volume_ratio,
                "real_money_execution":"DISABLED"}
