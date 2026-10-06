from __future__ import annotations

import hashlib
import os
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path
from typing import Any


def _now_dt(): return datetime.now(timezone.utc)
def _now(): return _now_dt().isoformat()
def _f(v):
    try:return float(v)
    except Exception:return None

def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class MobileApprovalStore:
    def __init__(self,path="data/baby_ui.db"):
        self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True); self._init()
    def _db(self):
        db=sqlite3.connect(self.path,timeout=30); db.row_factory=sqlite3.Row; return db
    def _init(self):
        with self._db() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS v1511_paper_approvals(
              id INTEGER PRIMARY KEY AUTOINCREMENT,symbol TEXT NOT NULL,ready_episode INTEGER NOT NULL,
              token_hash TEXT NOT NULL UNIQUE,status TEXT NOT NULL DEFAULT 'PENDING',created_at TEXT NOT NULL,expires_at TEXT NOT NULL,
              opened_at TEXT,revalidated_at TEXT,approved_at TEXT,used_at TEXT,cancelled_at TEXT,
              quantity REAL,alpaca_order_id TEXT,last_reason TEXT,
              UNIQUE(symbol,ready_episode))""")
            db.commit()
    def create(self,symbol,episode,ttl_minutes=None):
        ttl=int(ttl_minutes or os.getenv("BABY_PAPER_APPROVAL_TTL_MINUTES","180"))
        expires=(_now_dt()+timedelta(minutes=max(5,min(ttl,600)))).isoformat()
        token=secrets.token_urlsafe(32)
        with self._db() as db:
            existing=db.execute("SELECT * FROM v1511_paper_approvals WHERE symbol=? AND ready_episode=?",(symbol.upper(),int(episode))).fetchone()
            if existing:
                return None
            db.execute("INSERT INTO v1511_paper_approvals(symbol,ready_episode,token_hash,status,created_at,expires_at) VALUES(?,?,?,?,?,?)",
                       (symbol.upper(),int(episode),_hash(token),"PENDING",_now(),expires))
            db.commit()
        return token
    def by_token(self,token,mark_open=False):
        with self._db() as db:
            row=db.execute("SELECT * FROM v1511_paper_approvals WHERE token_hash=?",(_hash(token),)).fetchone()
            if not row:return None
            d=dict(row)
            if mark_open and not d.get('opened_at'):
                db.execute("UPDATE v1511_paper_approvals SET opened_at=? WHERE id=?",(_now(),d['id'])); db.commit(); d['opened_at']=_now()
        return d
    def latest_for_symbol(self,symbol):
        with self._db() as db:
            row=db.execute("SELECT * FROM v1511_paper_approvals WHERE symbol=? ORDER BY id DESC LIMIT 1",(symbol.upper(),)).fetchone()
        return dict(row) if row else None
    def expire_if_needed(self,row):
        if not row:return row
        try: expired=datetime.fromisoformat(row['expires_at'])<_now_dt()
        except Exception: expired=False
        if expired and row.get('status')=='PENDING':
            with self._db() as db:
                db.execute("UPDATE v1511_paper_approvals SET status='EXPIRED',last_reason=? WHERE id=?",('Approval window expired.',row['id']));db.commit()
            row=dict(row);row['status']='EXPIRED';row['last_reason']='Approval window expired.'
        return row
    def mark_revalidated(self,row_id,reason=None):
        with self._db() as db:
            db.execute("UPDATE v1511_paper_approvals SET revalidated_at=?,last_reason=? WHERE id=?",(_now(),reason,row_id));db.commit()
    def claim_for_execution(self,row_id,qty):
        now=_now()
        with self._db() as db:
            cur=db.execute(
                "UPDATE v1511_paper_approvals "
                "SET status='EXECUTING',approved_at=?,quantity=?,last_reason=? "
                "WHERE id=? AND status='PENDING'",
                (now,qty,'Submission claimed; awaiting Alpaca PAPER response.',row_id)
            )
            db.commit()
            return cur.rowcount==1

    def mark_submit_unknown(self,row_id,reason):
        with self._db() as db:
            db.execute(
                "UPDATE v1511_paper_approvals "
                "SET status='SUBMIT_UNKNOWN',last_reason=? "
                "WHERE id=? AND status='EXECUTING'",
                (str(reason or 'Broker submission result is unknown.'),row_id)
            )
            db.commit()

    def mark_used(self,row_id,qty,order_id):
        with self._db() as db:
            db.execute(
                "UPDATE v1511_paper_approvals "
                "SET status='USED',approved_at=COALESCE(approved_at,?),used_at=?,"
                "quantity=?,alpaca_order_id=?,last_reason=? "
                "WHERE id=? AND status='EXECUTING'",
                (_now(),_now(),qty,str(order_id or ''),'Alpaca PAPER order submitted.',row_id)
            )
            db.commit()
    def list(self,limit=100):
        with self._db() as db:
            rows=db.execute("""SELECT id,symbol,ready_episode,status,created_at,expires_at,opened_at,
                                      revalidated_at,approved_at,used_at,cancelled_at,quantity,
                                      alpaca_order_id,last_reason
                               FROM v1511_paper_approvals
                               ORDER BY id DESC LIMIT ?""",
                            (max(1,min(int(limit),500)),)).fetchall()
        return [dict(r) for r in rows]


def public_base_url() -> str:
    return os.getenv("BABY_PUBLIC_BASE_URL","https://jarvis-dl2.pages.dev").rstrip('/')


def approval_url(token: str) -> str:
    return f"{public_base_url()}/api/paper-approval/{token}"


def validate_user_quantity(qty,proposal,account):
    try:q=int(qty)
    except Exception:return False,"Quantity must be a positive whole-share number.",{}
    if q<=0:return False,"Quantity must be greater than zero.",{}
    px=_f(proposal.get('quote_price')) or _f(proposal.get('entry_price'))
    stop=_f(proposal.get('invalidation'))
    if not px or px<=0:return False,"Current proposal does not have a valid execution price.",{}
    equity=_f(account.get('equity'));cash=_f(account.get('cash'));bp=_f(account.get('buying_power'))
    notional=q*px
    available=min([x for x in (cash,bp) if x is not None],default=None)
    if available is not None and notional>available+1e-9:
        return False,"User-selected quantity exceeds current Alpaca PAPER cash/buying power.",{"notional":notional,"available":available}
    max_pct=float(os.getenv('BABY_PAPER_MAX_POSITION_PERCENT','10'))/100.0
    if equity is not None and max_pct>0 and notional>equity*max_pct+1e-9:
        return False,"User-selected quantity exceeds Baby's configured PAPER max-position gate.",{"notional":notional,"max_position_dollars":equity*max_pct}
    risk_per_share=(px-stop) if stop is not None and stop<px else None
    risk_pct=float(os.getenv('BABY_PAPER_RISK_PERCENT','0.5'))/100.0
    user_risk=q*risk_per_share if risk_per_share is not None else None
    if equity is not None and user_risk is not None and risk_pct>0 and user_risk>equity*risk_pct+1e-9:
        return False,"User-selected quantity exceeds Baby's configured PAPER risk-at-invalidation gate.",{"user_risk_dollars":user_risk,"max_risk_dollars":equity*risk_pct}
    return True,"PASS",{"quantity":q,"notional":notional,"user_risk_dollars":user_risk,"quantity_source":"USER_SELECTED"}


def mobile_html(row:dict, proposal:dict, message:str="") -> str:
    e=escape
    eligible=bool(proposal.get('eligible')) and str(proposal.get('status') or '').upper()=='ELIGIBLE'
    state='PAPER SETUP READY' if eligible else 'SETUP NOT CURRENTLY READY'
    bg='#0f6b3d' if eligible else '#7f1d1d'
    token_note='This approval is single-use and is revalidated again immediately before any Alpaca PAPER submission.'
    def m(v):
        try:return f"${float(v):,.2f}"
        except Exception:return '--'
    rows=''.join(f"<tr><td>{e(k)}</td><td><b>{e(v)}</b></td></tr>" for k,v in [
        ('Current quote',m(proposal.get('quote_price'))),('Entry',m(proposal.get('entry_price'))),('Invalidation',m(proposal.get('invalidation'))),
        ('Target 1',m(proposal.get('target_1'))),('Target 2',m(proposal.get('target_2'))),('R/R T1',str(proposal.get('rr_target_1') or '--')),('R/R T2',str(proposal.get('rr_target_2') or '--'))])
    controls='''<div class="box"><label>Shares (you choose)</label><input id="qty" inputmode="numeric" type="number" min="1" step="1" placeholder="Enter whole shares"><label>Confirmation</label><input id="confirm" placeholder="Type: EXECUTE ALPACA PAPER"><button onclick="go()">CONFIRM ALPACA PAPER</button><div id="result"></div></div>''' if eligible and row.get('status')=='PENDING' else ''
    js=f'''<script>async function go(){{const q=document.getElementById('qty').value;const c=document.getElementById('confirm').value;const r=await fetch('/api/paper-approval/{e(row.get('plain_token',''))}/execute',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{quantity:q,confirmation:c}})}});const t=await r.text();document.getElementById('result').innerText=t;if(r.ok) setTimeout(()=>location.reload(),1200);}}</script>''' if controls else ''
    return f'''<!doctype html><html><meta name="viewport" content="width=device-width,initial-scale=1"><body style="margin:0;background:#07111c;color:#eaf4ff;font-family:Arial,sans-serif"><main style="max-width:560px;margin:auto;padding:18px"><div style="background:{bg};padding:20px;border-radius:16px"><div style="font-size:12px;letter-spacing:.12em;font-weight:800">{state}</div><h1 style="margin:8px 0">{e(row.get('symbol',''))}</h1><div>Episode {e(row.get('ready_episode',''))} · {e(row.get('status',''))}</div></div>{f'<div style="margin:14px 0;padding:12px;background:#3b1f1f;border-radius:10px">{e(message)}</div>' if message else ''}<div style="background:#0d1d2c;padding:16px;border-radius:14px;margin-top:14px"><table style="width:100%;border-collapse:collapse">{rows}</table><p style="color:#9db2c5">{e(proposal.get('reason') or '')}</p></div><style>td{{padding:9px 4px;border-bottom:1px solid #1d3447}}label{{display:block;margin-top:12px;color:#aac0d3}}input{{width:100%;box-sizing:border-box;padding:13px;margin-top:6px;border-radius:9px;border:1px solid #35506a;background:#07111c;color:white}}button{{width:100%;padding:14px;margin-top:16px;border:0;border-radius:10px;background:#22c55e;color:#052512;font-weight:900}}.box{{background:#0d1d2c;padding:16px;border-radius:14px;margin-top:14px}}</style>{controls}<p style="font-size:12px;color:#7890a5;margin-top:18px">{token_note}<br>AI execution authority: NONE · Real-money execution: DISABLED.</p></main>{js}</body></html>'''
