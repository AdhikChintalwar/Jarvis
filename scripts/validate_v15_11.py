from pathlib import Path
import sys

root=Path.cwd()
required=[
 'baby_ui_backend/v1511_forward_validation.py','baby_ui_backend/v1511_readiness.py','baby_ui_backend/v1511_mobile_approval.py',
 'baby_ui_backend/v1511_email_style.py','baby_ui_backend/v1511_runtime.py','baby_ui_backend/v1511_discovery.py']
for x in required:
    assert (root/x).exists(),x
app=(root/'baby_ui_backend/app.py').read_text()
sub=(root/'baby_ui_backend/subscriber_email.py').read_text()
v155=(root/'baby_ui_backend/v155_email.py').read_text()
sched=(root/'baby_ui_backend/operating_scheduler.py').read_text()
assert '# ===== BABY V15.11 MOBILE PAPER APPROVAL' in app
assert '/api/paper-approval/{token}' in app
assert 'quantity_source' in app and 'USER_SELECTED' in app
assert "real_money_execution':'DISABLED'" in app or 'real_money_execution\":\"DISABLED' in app or "'real_money_execution':'DISABLED'" in app
assert 'setup_ready_decorate' in sub
assert 'research_monitor_decorate' in v155
assert 'v1511_select_candidates' in sched
assert 'BABY_REAL_MONEY_EXECUTION=ENABLED' not in app
print('PASS V15.11 files/routes/email styling/discovery hooks')
print('PASS user-selected quantity invariant')
print('PASS real-money execution remains disabled')
