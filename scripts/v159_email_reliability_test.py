#!/usr/bin/env python3
from pathlib import Path
import tempfile,sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from baby_ui_backend.subscriber_email import SubscriberStore

def main():
    with tempfile.TemporaryDirectory() as td:
        s=SubscriberStore(Path(td)/"baby.db")
        now="2026-09-24T00:00:00+00:00"
        with s._db() as c:
            c.execute("INSERT INTO email_subscribers(email,status,created_at,updated_at,verified_at) VALUES(?,?,?,?,?)",
                      ("test@example.com","VERIFIED",now,now,now))
            sid=c.execute("SELECT id FROM email_subscribers WHERE email='test@example.com'").fetchone()[0]
            c.commit()

        assert s.observe_candidate_state("TEST","SETUP_READY",True)["ready_episode"]==1
        assert s.observe_candidate_state("TEST","SETUP_READY",True)["ready_episode"]==1
        s.observe_candidate_state("TEST","MONITOR",False)
        assert s.observe_candidate_state("TEST","SETUP_READY",True)["ready_episode"]==2
        print("PASS ready_episode_stable")

        key="setup-ready:TEST:episode:2:SETUP_READY"
        s.record_delivery(sid,"test@example.com","TEST","SETUP_READY",key,"FAILED","subject","boom")
        assert s.delivery_exists(sid,key) is False
        row=s.delivery_row(sid,key)
        assert row["delivery_status"]=="FAILED" and int(row["attempt_count"])==1
        print("PASS failed_not_sent")

        allowed,reason=s.retry_allowed(sid,key,300,3)
        assert allowed is False and reason=="RETRY_COOLDOWN"
        print("PASS retry_cooldown")

        allowed,reason=s.retry_allowed(sid,key,0,3)
        assert allowed is True and reason=="RETRY"
        s.record_delivery(sid,"test@example.com","TEST","SETUP_READY",key,"SENT","subject")
        row=s.delivery_row(sid,key)
        assert row["delivery_status"]=="SENT" and int(row["attempt_count"])==2
        print("PASS retry_success")

        allowed,reason=s.retry_allowed(sid,key,0,3)
        assert allowed is False and reason=="ALREADY_SENT"
        print("PASS sent_dedupe")

        key2="setup-ready:TEST:episode:3:SETUP_READY"
        for _ in range(3):
            s.record_delivery(sid,"test@example.com","TEST","SETUP_READY",key2,"FAILED","subject","boom")
        assert int(s.delivery_row(sid,key2)["attempt_count"])==3
        allowed,reason=s.retry_allowed(sid,key2,0,3)
        assert allowed is False and reason=="MAX_ATTEMPTS"
        print("PASS max_attempts")

    print("V15.9.0b email reliability test PASS")

if __name__=="__main__":
    main()
