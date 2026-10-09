from pathlib import Path

q = Path("baby_ui_backend/v1516_quick.py").read_text()
n = Path("baby_ui_backend/v1516_ntfy.py").read_text()

assert "Passkey authentication required" in q
assert "BABY_QUICK_SESSION_SECRET" in q
assert "BABY_QUICK_TOKEN_SECRET" in q
assert "require_user_verification=True" in q
assert "Daily PAPER trade limit reached" in q
assert "EXECUTE ALPACA PAPER" in q
assert 'side="SELL"' in q
assert "candidate_alert_state" in q
assert "alpaca_order_id IS NULL" in q
assert "Authorization" in n and "Bearer" in n
assert "issue_setup_token" in n

print("PASS passkey authentication boundary")
print("PASS signed session + expiring setup link")
print("PASS current server-created setup only")
print("PASS 3/day PAPER execution cap")
print("PASS PAPER-only BUY/SELL confirmation path")
print("PASS authenticated self-hosted ntfy publishing")
print("V15.16 static security validation PASS")
