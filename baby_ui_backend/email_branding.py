from __future__ import annotations
from pathlib import Path
from html import escape
from datetime import datetime
from zoneinfo import ZoneInfo

ET=ZoneInfo("America/New_York")

def _e(x): return escape("" if x is None else str(x))

def email_shell(title:str,preheader:str,body_html:str)->str:
    now=datetime.now(ET).strftime("%b %d, %Y · %I:%M %p ET")
    return f"""<!doctype html><html><body style="margin:0;background:#eef4fb;font-family:Arial,Helvetica,sans-serif;color:#102a43">
<div style="display:none;max-height:0;overflow:hidden">{_e(preheader)}</div>
<table width="100%" cellspacing="0" cellpadding="0" style="background:#eef4fb"><tr><td align="center" style="padding:28px 14px">
<table width="100%" cellspacing="0" cellpadding="0" style="max-width:640px;background:#ffffff;border:1px solid #d7e3ef;border-radius:18px">
<tr><td align="center" style="padding:20px 24px;border-bottom:1px solid #d7e3ef"><img src="cid:baby-logo" alt="BABY" style="display:block;width:260px;max-width:78%;height:auto;border:0"></td></tr>
<tr><td style="padding:24px"><div style="font-size:11px;letter-spacing:.14em;color:#1769aa;font-weight:800">{_e(title.upper())}</div>{body_html}</td></tr>
<tr><td style="padding:18px 24px;border-top:1px solid #d7e3ef;color:#627d98;font-size:11px;line-height:1.6">Research and monitoring only. Email cannot place an order.<br>AI execution authority: NONE · Real-money execution: DISABLED<br>{now}</td></tr>
</table></td></tr></table></body></html>"""

def verification_html(code,minutes=30):
    return email_shell("Email verification","Verify your Baby research alerts.",f"""<h1 style="font-size:26px;margin:12px 0">Verify Baby alerts</h1>
<p style="color:#526d82">Use this code to verify your email for Baby research notifications.</p>
<div style="margin:24px 0;padding:20px;text-align:center;border:1px solid #cbd9e6;background:#f4f8fc;border-radius:14px;font-size:34px;letter-spacing:.18em;font-weight:800">{_e(code)}</div>
<p style="color:#7c93a8">Expires in {_e(minutes)} minutes.</p>""")

BABY_EMAIL_LOGO_CID = "baby-logo"
BABY_EMAIL_LOGO_PATH = Path(__file__).resolve().parent / "assets" / "baby-logo.png"
