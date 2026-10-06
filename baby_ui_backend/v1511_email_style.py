from __future__ import annotations

from html import escape
from .v1511_mobile_approval import approval_url
from .v1511_runtime import approval_token_for


def setup_ready_decorate(html_body:str,symbol:str,paper:dict) -> str:
    token=approval_token_for(symbol)
    button=''
    if token:
        url=approval_url(token)
        button=f'''<div style="margin:18px 0"><a href="{escape(url)}" style="display:inline-block;background:#22c55e;color:#052512;text-decoration:none;font-weight:900;padding:13px 18px;border-radius:10px">REVIEW / APPROVE ALPACA PAPER</a></div>'''
    banner='''<div style="margin:0 0 18px;padding:18px;border-radius:14px;background:#0f6b3d;color:#ffffff"><div style="font-size:12px;font-weight:900;letter-spacing:.13em">PAPER SETUP READY</div><div style="margin-top:7px;font-size:13px">Trade quality and current deterministic PAPER eligibility passed at alert time. Revalidation is still required before submission.</div></div>'''
    return banner+button+html_body


def research_monitor_decorate(html_body:str,event:str) -> str:
    title=str(event or 'RESEARCH MONITOR').replace('_',' ')
    banner=f'''<div style="margin:0 0 18px;padding:18px;border-radius:14px;background:#7f1d1d;color:#ffffff"><div style="font-size:12px;font-weight:900;letter-spacing:.13em">RESEARCH MONITOR — NOT PAPER READY</div><div style="margin-top:7px;font-size:13px">{escape(title)} means Baby finds this worth monitoring. It is not an eligible PAPER entry.</div></div>'''
    return banner+html_body
