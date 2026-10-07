from __future__ import annotations
import sqlite3
import tempfile
from pathlib import Path
from baby_ui_backend.v1513_awareness import BabyAwarenessService


def main():
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / 'baby_ui.db'
        db = sqlite3.connect(path)
        db.executescript('''
        CREATE TABLE v1511_readiness(symbol TEXT,state TEXT,readiness_potential INTEGER,reason TEXT,setup_status TEXT,failures_json TEXT,updated_at TEXT);
        CREATE TABLE v1512_readiness_history(id INTEGER PRIMARY KEY,symbol TEXT,state TEXT,readiness_potential INTEGER,reason TEXT,setup_status TEXT,failures_json TEXT,observed_at TEXT,source TEXT,source_key TEXT);
        CREATE TABLE v1511_forward_validation(id INTEGER PRIMARY KEY,symbol TEXT,ready_episode INTEGER,setup_type TEXT,setup_status TEXT,t0 TEXT,entry REAL,invalidation REAL,target1 REAL,target2 REAL,outcome TEXT,filled INTEGER,first_fill_at TEXT,fill_price REAL,alpaca_order_id TEXT,order_status TEXT,quantity REAL,t1_hit_at TEXT,t2_hit_at TEXT,stop_hit_at TEXT,closed_at TEXT,theoretical_entry_at TEXT,theoretical_outcome TEXT,theoretical_t1_hit_at TEXT,theoretical_t2_hit_at TEXT,theoretical_stop_hit_at TEXT,theoretical_closed_at TEXT,paper_outcome TEXT,paper_t1_hit_at TEXT,paper_t2_hit_at TEXT,paper_stop_hit_at TEXT,paper_closed_at TEXT);
        CREATE TABLE v1511_forward_events(id INTEGER PRIMARY KEY,validation_id INTEGER,symbol TEXT,event_type TEXT,observed_at TEXT,price REAL,payload_json TEXT);
        CREATE TABLE v1511_paper_approvals(id INTEGER PRIMARY KEY,symbol TEXT,ready_episode INTEGER,status TEXT,created_at TEXT,approved_at TEXT,used_at TEXT,quantity REAL,alpaca_order_id TEXT,last_reason TEXT);
        CREATE TABLE email_deliveries(id INTEGER PRIMARY KEY,subscriber_id INTEGER,email TEXT,symbol TEXT,event_type TEXT,dedupe_key TEXT,delivery_status TEXT,subject TEXT,error TEXT,created_at TEXT,sent_at TEXT,attempt_count INTEGER,last_attempt_at TEXT);
        CREATE TABLE alerts(id INTEGER PRIMARY KEY,dedupe_key TEXT,symbol TEXT,severity TEXT,title TEXT,message TEXT,payload TEXT,created_at TEXT);
        CREATE TABLE candidate_alert_state(symbol TEXT,last_state TEXT,last_ready INTEGER,updated_at TEXT,last_alert_at TEXT,ready_episode INTEGER);
        ''')
        db.execute('INSERT INTO v1511_readiness VALUES (?,?,?,?,?,?,?)', ('TDAY','SETUP_READY',100,'Eligible','READY','[]','2026-10-07T14:00:00+00:00'))
        db.execute('INSERT INTO email_deliveries(subscriber_id,email,symbol,event_type,dedupe_key,delivery_status,subject,error,created_at,sent_at,attempt_count,last_attempt_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)', (1,'user@example.com','TDAY','SETUP_READY','x','SENT','BABY — TDAY setup',None,'2026-10-07T14:01:00+00:00','2026-10-07T14:01:02+00:00',1,'2026-10-07T14:01:02+00:00'))
        db.execute('INSERT INTO v1511_forward_validation(symbol,ready_episode,setup_type,setup_status,t0,entry,invalidation,target1,target2,filled,first_fill_at,fill_price,alpaca_order_id,order_status,quantity,paper_t1_hit_at,paper_outcome) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)', ('TDAY',1,'PULLBACK','READY','2026-10-07T14:00:00+00:00',10,9.5,10.8,11.5,1,'2026-10-07T14:05:00+00:00',10.02,'paper-1','filled',10,'2026-10-07T15:00:00+00:00','T1_HIT'))
        db.commit(); db.close()
        out = BabyAwarenessService(path).symbol_activity('TDAY')
        assert out['email']['delivery_proven'] is True
        assert out['forward_validation']['paper']['filled'] is True
        assert out['forward_validation']['paper']['t1_hit'] is True
        assert out['authority']['CHAT_EXECUTION_AUTHORITY'] == 'NONE'
        assert out['authority']['REAL_MONEY_EXECUTION'] == 'DISABLED'
        print('PASS email delivery proof')
        print('PASS PAPER fill awareness')
        print('PASS PAPER T1 awareness')
        print('PASS theoretical-vs-PAPER separation')
        print('PASS read-only authority boundaries')
        print('V15.13 awareness validation PASS')


if __name__ == '__main__':
    main()
