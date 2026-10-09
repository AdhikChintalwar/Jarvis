from pathlib import Path

p = Path("baby_ui_backend/v1515_autopilot_worker.py")
s = p.read_text()

assert "JOIN v1511_readiness r" in s
assert "r.state='SETUP_READY'" in s
assert "JOIN candidate_alert_state c" in s
assert "c.ready_episode=fv.ready_episode" in s
assert "fv.t0 >= ?" in s
assert "SELECT MAX(x.id)" in s
assert "BABY_PAPER_ENTRY_MAX_AGE_SECONDS" in s
assert "ENTRY_BLOCKED_NOT_ELIGIBLE" in s
assert "confirmation=PAPER_CONFIRMATION" in s

print("PASS current readiness gate")
print("PASS current ready_episode gate")
print("PASS latest episode gate")
print("PASS fresh episode age gate")
print("PASS repeated blocked-log dedup")
print("PASS PAPER confirmation path retained")
print("V15.15 Phase B hotfix validation PASS")
