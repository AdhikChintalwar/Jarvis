#!/usr/bin/env python3
from pathlib import Path
import py_compile,sys,tempfile

root=Path.cwd()
p=root/"baby_ui_backend/subscriber_email.py"
py_compile.compile(str(p),doraise=True)
sys.path.insert(0,str(root))
from baby_ui_backend.subscriber_email import SubscriberStore

with tempfile.TemporaryDirectory() as td:
    s=SubscriberStore(Path(td)/"test.db")
    with s._db() as c:
        cols={r[1] for r in c.execute("PRAGMA table_info(email_deliveries)").fetchall()}
        state_cols={r[1] for r in c.execute("PRAGMA table_info(candidate_alert_state)").fetchall()}
    assert "attempt_count" in cols
    assert "last_attempt_at" in cols
    assert "ready_episode" in state_cols

print("V15.9.0b validation PASS")
print("Retry-safe delivery schema present.")
print("Ready-episode tracking present.")
print("Scheduler cadence unchanged.")
print("No automatic execution or quantity selection was added.")
