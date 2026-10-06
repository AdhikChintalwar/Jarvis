from pathlib import Path
import tempfile
from baby_ui_backend.v1511_forward_validation import ForwardValidationLedger
from baby_ui_backend.v1511_mobile_approval import MobileApprovalStore

tmp=Path(tempfile.mkdtemp())/"x.db"
l=ForwardValidationLedger(tmp)

# Not at entry at T0 => theoretical UNFILLED. A target-like price before entry
# must not count as a successful trade.
p={
    "setup_type":"FLOW_ONLY","setup_status":"AT_PULLBACK_ZONE","status":"ELIGIBLE","eligible":True,
    "entry_price":100.0,"quote_price":105.0,"invalidation":95.0,"target_1":110.0,"target_2":120.0,
    "rr_target_1":2.0,"rr_target_2":4.0,
}
r=l.record_ready("TEST",1,p,{})
assert r["theoretical_outcome"]=="UNFILLED",r
l.observe_price("TEST",111.0,"2026-10-06T14:00:00+00:00")
r=l.list(1)[0]
assert r["theoretical_outcome"]=="UNFILLED",r
assert r["theoretical_t1_hit_at"] is None,r
print("PASS no_target_before_theoretical_entry")

# Entry touch activates theoretical grading.
l.observe_price("TEST",99.5,"2026-10-06T14:01:00+00:00")
r=l.list(1)[0]
assert r["theoretical_outcome"]=="OPEN",r
assert r["theoretical_entry_at"],r
l.observe_price("TEST",110.5,"2026-10-06T14:02:00+00:00")
r=l.list(1)[0]
assert r["theoretical_outcome"]=="T1_HIT",r
print("PASS theoretical_entry_then_t1")

# PAPER track must remain NOT_EXECUTED until an order, UNFILLED until broker fill.
assert r["paper_outcome"]=="NOT_EXECUTED",r
l.attach_order("TEST",1,{"id":"paper-1","status":"accepted"},2)
r=l.list(1)[0]
assert r["paper_outcome"]=="UNFILLED",r
l.observe_price("TEST",120.5,"2026-10-06T14:03:00+00:00")
r=l.list(1)[0]
assert r["paper_outcome"]=="UNFILLED",r
assert r["paper_t1_hit_at"] is None,r
print("PASS no_paper_success_before_broker_fill")

l.record_fill("TEST",1,101.0,"2026-10-06T14:04:00+00:00")
r=l.list(1)[0]
assert r["paper_outcome"]=="OPEN",r
l.observe_price("TEST",110.5,"2026-10-06T14:05:00+00:00")
r=l.list(1)[0]
assert r["paper_outcome"]=="T1_HIT",r
assert r["paper_mfe_pct"] is not None,r
print("PASS paper_metrics_start_after_fill")

a=MobileApprovalStore(tmp)
tok=a.create("ABC",1)
assert tok
rows=a.list()
assert rows and "token_hash" not in rows[0], rows[0]
print("PASS approval_list_redacts_token_hash")

print("V15.11.0a validation correctness fix PASS")
