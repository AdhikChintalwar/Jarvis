from pathlib import Path
import tempfile
import threading

from baby_ui_backend.v1511_mobile_approval import MobileApprovalStore

tmp = Path(tempfile.mkdtemp()) / "x.db"
store = MobileApprovalStore(tmp)

token = store.create("RACE", 1, 30)
row = store.by_token(token)
assert row and row["status"] == "PENDING"

results = []
barrier = threading.Barrier(3)

def worker():
    barrier.wait()
    results.append(store.claim_for_execution(row["id"], 5))

a = threading.Thread(target=worker)
b = threading.Thread(target=worker)
a.start()
b.start()
barrier.wait()
a.join()
b.join()

assert sorted(results) == [False, True], results
row = store.by_token(token)
assert row["status"] == "EXECUTING", row
print("PASS atomic_single_use_claim")

store.mark_submit_unknown(row["id"], "simulated timeout")
row = store.by_token(token)
assert row["status"] == "SUBMIT_UNKNOWN", row
assert not store.claim_for_execution(row["id"], 5)
print("PASS uncertain_submission_fails_closed")

token2 = store.create("OK", 1, 30)
row2 = store.by_token(token2)
assert store.claim_for_execution(row2["id"], 2)
store.mark_used(row2["id"], 2, "paper-order-123")
row2 = store.by_token(token2)
assert row2["status"] == "USED", row2
assert row2["alpaca_order_id"] == "paper-order-123", row2
assert not store.claim_for_execution(row2["id"], 2)
print("PASS used_approval_cannot_be_reused")

print("V15.11.0c approval single-use race fix PASS")
