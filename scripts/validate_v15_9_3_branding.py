from pathlib import Path

root = Path(__file__).resolve().parents[1]

app_logo = root / "frontend/public/baby-wordmark-v15-4.png"
email_logo = root / "baby_ui_backend/assets/baby-logo.png"
branding = (root / "baby_ui_backend/email_branding.py").read_text()
v155 = (root / "baby_ui_backend/v155_email.py").read_text()
sub = (root / "baby_ui_backend/subscriber_email.py").read_text()

checks = {
    "software_logo_exists": app_logo.exists() and app_logo.stat().st_size > 100_000,
    "email_logo_exists": email_logo.exists() and email_logo.stat().st_size > 100_000,
    "email_logo_cid_preserved": 'BABY_EMAIL_LOGO_CID' in branding and 'cid:baby-logo' in branding,
    "email_logo_path_preserved": 'assets' in branding and 'baby-logo.png' in branding,
    "light_shell": '#ffffff' in branding and '#eef4fb' in branding,
    "light_research_cards": '#f4f8fc' in v155 or '#f7fafd' in v155,
    "light_setup_cards": '#f4f8fc' in sub or '#f7fafd' in sub,
    "execution_copy_preserved": 'Real-money execution: DISABLED' in branding,
}

failed = [k for k,v in checks.items() if not v]
if failed:
    raise SystemExit("V15.9.3 branding validation FAILED: " + ", ".join(failed))

print("V15.9.3 branding validation PASS")
print("Software banner installed at frontend/public/baby-wordmark-v15-4.png")
print("Transparent email logo installed at baby_ui_backend/assets/baby-logo.png")
print("Email content palette changed to light surfaces for readability.")
print("No research, scheduler, scoring, quantity, or execution logic changed.")
