from pathlib import Path
import tempfile, sqlite3
from datetime import datetime, timezone
from baby_ui_backend.v1512_reports import ReportService, build_pdf, theoretical_status, paper_status

tmp=Path(tempfile.mkdtemp())/"r.db"
svc=ReportService(tmp)
db=sqlite3.connect(tmp)
db.execute("""CREATE TABLE v1511_forward_validation(
 id INTEGER PRIMARY KEY,symbol TEXT,ready_episode INTEGER,setup_type TEXT,t0 TEXT,entry REAL,invalidation REAL,target1 REAL,target2 REAL,
 theoretical_entry_at TEXT,theoretical_outcome TEXT,theoretical_mfe_pct REAL,theoretical_mae_pct REAL,
 theoretical_t1_hit_at TEXT,theoretical_t2_hit_at TEXT,theoretical_stop_hit_at TEXT,theoretical_closed_at TEXT,
 paper_outcome TEXT,alpaca_order_id TEXT,quantity REAL,filled INTEGER,first_fill_at TEXT,fill_price REAL,
 paper_t1_hit_at TEXT,paper_t2_hit_at TEXT,paper_stop_hit_at TEXT,paper_mfe_pct REAL,paper_mae_pct REAL)""")
db.execute("""CREATE TABLE v1511_paper_approvals(id INTEGER PRIMARY KEY,symbol TEXT,ready_episode INTEGER,status TEXT,created_at TEXT)""")
db.execute("""CREATE TABLE email_deliveries(id INTEGER PRIMARY KEY,event_type TEXT,delivery_status TEXT,created_at TEXT)""")
now=datetime.now(timezone.utc).isoformat()
db.execute("""INSERT INTO v1511_forward_validation VALUES(
1,'AAPL',1,'BREAKOUT',?,24.93,23.81,26.46,28.40,
?,'T1_HIT',7.1,-1.2,
?,NULL,NULL,NULL,
'NOT_EXECUTED',NULL,NULL,0,NULL,NULL,NULL,NULL,NULL,NULL,NULL)""",(now,now,now))
db.execute("""INSERT INTO v1512_readiness_history(symbol,state,readiness_potential,reason,setup_status,failures_json,observed_at)
VALUES('AAPL','SETUP_READY',100,'ready','AT_PULLBACK_ZONE','[]',?)""",(now,))
db.commit();db.close()

d=svc.overview(3650)
assert d["baby_performance"][0]["status"]=="PARTIAL_SUCCESS"
assert d["baby_performance"][0]["t1_hit_at"]
assert d["baby_performance"][0]["paper_status"]=="NOT_TRADED"
assert theoretical_status("T2_HIT")=="SUCCESS"
assert theoretical_status("STOPPED")=="FAILED"
assert paper_status("NOT_EXECUTED",False)=="NOT_TRADED"
pdf=build_pdf(d)
assert pdf.startswith(b"%PDF-")
print("PASS milestone dates and status mapping")
print("PASS Baby-vs-PAPER separation")
print("PASS PDF export generation")
print("V15.12 reports validation PASS")
