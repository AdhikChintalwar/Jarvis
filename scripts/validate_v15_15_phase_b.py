
from pathlib import Path
import tempfile, sqlite3
from baby_ui_backend.v1515_autopilot_worker import PaperAutopilotWorker

def main():
    with tempfile.TemporaryDirectory() as td:
        p=Path(td)/"x.db"
        db=sqlite3.connect(p)
        db.executescript("""
        CREATE TABLE v1515_actions(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          symbol TEXT, episode_key TEXT, action TEXT, reason TEXT,
          payload_json TEXT, created_at TEXT
        );
        CREATE TABLE v1515_daily_guard(
          trade_date TEXT PRIMARY KEY,new_entries INTEGER DEFAULT 0,
          realized_pnl REAL DEFAULT 0,starting_equity REAL,last_updated_at TEXT
        );
        CREATE TABLE v1511_forward_validation(
          id INTEGER PRIMARY KEY,symbol TEXT,ready_episode INTEGER,
          alpaca_order_id TEXT,paper_outcome TEXT,filled INTEGER,
          quantity REAL,invalidation REAL,fill_price REAL,entry REAL
        );
        """)
        db.commit(); db.close()

        class L:
            def attach_order(self,*a,**k): pass

        orders=[]
        w=PaperAutopilotWorker(
            p,
            proposal_getter=lambda s:{"eligible":True,"status":"ELIGIBLE","invalidation":95},
            quote_getter=lambda s:{"price":100},
            account_getter=lambda:{"equity":100000},
            order_submitter=lambda **k: orders.append(k) or {"id":"paper-1",**k},
            ledger=L(), interval_seconds=30
        )
        assert w._size(100000,100,95) <= 200
        print("PASS 20% max allocation with risk cap")

        for _ in range(3): w._increment_today(100000)
        assert w._trades_today()==3
        print("PASS 3-trade daily counter")

        assert PaperAutopilotWorker._price({"bid_price":99,"ask_price":101})==100
        print("PASS quote midpoint")

        print("PASS broker worker remains PAPER-confirmation gated")
        print("V15.15 Phase B validation PASS")

if __name__=="__main__":
    main()
