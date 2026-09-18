from __future__ import annotations

from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Any
import hashlib
import json
import os
import re
import secrets
import smtplib
import sqlite3
import ssl

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

def utcnow() -> datetime:
    return datetime.now(timezone.utc)

def iso(dt: datetime | None = None) -> str:
    return (dt or utcnow()).isoformat()

def _num(v):
    try: return float(v)
    except Exception: return None

def _money(v):
    n=_num(v); return "--" if n is None else f"${n:,.2f}"

def _rr(v):
    n=_num(v); return "--" if n is None else f"{n:.2f}x"

def _upper(v): return str(v or "").upper().strip()

class SubscriberStore:
    def __init__(self,path='data/baby_ui.db'):
        self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True); self._init()
    def _db(self):
        db=sqlite3.connect(self.path,timeout=30); db.row_factory=sqlite3.Row; return db
    def _init(self):
        with self._db() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS email_subscribers(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              email TEXT NOT NULL COLLATE NOCASE UNIQUE,
              status TEXT NOT NULL DEFAULT 'PENDING',
              verification_hash TEXT,
              verification_salt TEXT,
              verification_expires_at TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              verified_at TEXT,
              removed_at TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_email_subscribers_status ON email_subscribers(status);
            CREATE TABLE IF NOT EXISTS email_deliveries(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              subscriber_id INTEGER,
              email TEXT NOT NULL,
              symbol TEXT,
              event_type TEXT NOT NULL,
              dedupe_key TEXT NOT NULL,
              delivery_status TEXT NOT NULL,
              subject TEXT NOT NULL,
              error TEXT,
              created_at TEXT NOT NULL,
              sent_at TEXT
            );
            CREATE UNIQUE INDEX IF NOT EXISTS idx_email_delivery_dedupe ON email_deliveries(subscriber_id,dedupe_key);
            CREATE TABLE IF NOT EXISTS candidate_alert_state(
              symbol TEXT PRIMARY KEY,
              last_state TEXT,
              last_ready INTEGER NOT NULL DEFAULT 0,
              updated_at TEXT NOT NULL,
              last_alert_at TEXT
            );
            ''')
    @staticmethod
    def normalize_email(email):
        email=str(email or '').strip().lower()
        if len(email)>320 or not EMAIL_RE.match(email): raise ValueError('Enter a valid email address.')
        return email
    @staticmethod
    def _hash_code(code,salt): return hashlib.sha256(f'{salt}:{code}'.encode()).hexdigest()
    def create_pending(self,email,code,expires_minutes=30):
        email=self.normalize_email(email); now=utcnow(); salt=secrets.token_hex(16); code_hash=self._hash_code(code,salt)
        expiry=iso(now+timedelta(minutes=max(5,int(expires_minutes))))
        with self._db() as db:
            row=db.execute('SELECT id,status,created_at FROM email_subscribers WHERE email=?',(email,)).fetchone()
            if row and row['status']=='VERIFIED': return self.get(row['id'])
            created=row['created_at'] if row else iso(now)
            db.execute('''INSERT INTO email_subscribers(email,status,verification_hash,verification_salt,verification_expires_at,created_at,updated_at,verified_at,removed_at)
                          VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(email) DO UPDATE SET status='PENDING',verification_hash=excluded.verification_hash,verification_salt=excluded.verification_salt,verification_expires_at=excluded.verification_expires_at,updated_at=excluded.updated_at,verified_at=NULL,removed_at=NULL''',
                       (email,'PENDING',code_hash,salt,expiry,created,iso(now),None,None)); db.commit()
            sid=db.execute('SELECT id FROM email_subscribers WHERE email=?',(email,)).fetchone()['id']
        return self.get(sid)
    def get(self,sid):
        with self._db() as db:
            r=db.execute('SELECT id,email,status,created_at,updated_at,verified_at,verification_expires_at FROM email_subscribers WHERE id=?',(int(sid),)).fetchone()
        return dict(r) if r else None
    def get_by_email(self,email):
        email=self.normalize_email(email)
        with self._db() as db:
            r=db.execute('SELECT id,email,status,created_at,updated_at,verified_at,verification_expires_at FROM email_subscribers WHERE email=?',(email,)).fetchone()
        return dict(r) if r else None
    def list(self):
        with self._db() as db:
            rows=db.execute("SELECT id,email,status,created_at,updated_at,verified_at,verification_expires_at FROM email_subscribers WHERE status!='REMOVED' ORDER BY status='VERIFIED' DESC,email").fetchall()
        return [dict(r) for r in rows]
    def verified(self):
        with self._db() as db:
            rows=db.execute("SELECT id,email,status,created_at,updated_at,verified_at FROM email_subscribers WHERE status='VERIFIED' ORDER BY email").fetchall()
        return [dict(r) for r in rows]
    def verify(self,email,code):
        email=self.normalize_email(email); code=str(code or '').strip()
        if not re.fullmatch(r'\d{6}',code): raise ValueError('Verification code must be 6 digits.')
        with self._db() as db:
            row=db.execute("SELECT * FROM email_subscribers WHERE email=? AND status='PENDING'",(email,)).fetchone()
            if not row: raise ValueError('No pending verification exists for this email.')
            try: expiry=datetime.fromisoformat(str(row['verification_expires_at']).replace('Z','+00:00'))
            except Exception: raise ValueError('Verification code is invalid or expired.')
            if expiry<utcnow(): raise ValueError('Verification code expired. Resend a new code.')
            expected=self._hash_code(code,row['verification_salt'] or '')
            if not secrets.compare_digest(expected,row['verification_hash'] or ''): raise ValueError('Verification code is incorrect.')
            now=iso(); db.execute("UPDATE email_subscribers SET status='VERIFIED',verified_at=?,updated_at=?,verification_hash=NULL,verification_salt=NULL,verification_expires_at=NULL WHERE id=?",(now,now,row['id'])); db.commit(); sid=row['id']
        return self.get(sid)
    def remove(self,sid):
        with self._db() as db:
            row=db.execute('SELECT id FROM email_subscribers WHERE id=?',(int(sid),)).fetchone()
            if not row:return None
            now=iso(); db.execute("UPDATE email_subscribers SET status='REMOVED',removed_at=?,updated_at=?,verification_hash=NULL,verification_salt=NULL,verification_expires_at=NULL WHERE id=?",(now,now,int(sid))); db.commit()
        return {'id':int(sid),'status':'REMOVED'}
    def candidate_state(self,symbol):
        with self._db() as db:r=db.execute('SELECT * FROM candidate_alert_state WHERE symbol=?',(symbol.upper(),)).fetchone()
        return dict(r) if r else None
    def set_candidate_state(self,symbol,state,ready,alerted=False):
        now=iso(); symbol=symbol.upper()
        with self._db() as db:
            db.execute('''INSERT INTO candidate_alert_state(symbol,last_state,last_ready,updated_at,last_alert_at) VALUES(?,?,?,?,?)
                          ON CONFLICT(symbol) DO UPDATE SET last_state=excluded.last_state,last_ready=excluded.last_ready,updated_at=excluded.updated_at,last_alert_at=CASE WHEN excluded.last_alert_at IS NOT NULL THEN excluded.last_alert_at ELSE candidate_alert_state.last_alert_at END''',
                       (symbol,state,1 if ready else 0,now,now if alerted else None)); db.commit()
    def delivery_exists(self,sid,key):
        with self._db() as db:return db.execute('SELECT 1 FROM email_deliveries WHERE subscriber_id=? AND dedupe_key=? LIMIT 1',(int(sid),key)).fetchone() is not None
    def record_delivery(self,sid,email,symbol,event_type,key,status,subject,error=None):
        now=iso()
        with self._db() as db:
            db.execute('''INSERT OR IGNORE INTO email_deliveries(subscriber_id,email,symbol,event_type,dedupe_key,delivery_status,subject,error,created_at,sent_at) VALUES(?,?,?,?,?,?,?,?,?,?)''',
                       (sid,email,symbol,event_type,key,status,subject,error,now,now if status=='SENT' else None)); db.commit()
    def deliveries(self,limit=100):
        with self._db() as db:rows=db.execute('SELECT id,subscriber_id,email,symbol,event_type,dedupe_key,delivery_status,subject,error,created_at,sent_at FROM email_deliveries ORDER BY id DESC LIMIT ?',(min(max(int(limit),1),500),)).fetchall()
        return [dict(r) for r in rows]

class SMTPMailer:
    def __init__(self):
        self.enabled=os.getenv('BABY_EMAIL_ENABLED','DISABLED').upper()=='ENABLED'; self.host=os.getenv('BABY_SMTP_HOST','').strip(); self.port=int(os.getenv('BABY_SMTP_PORT','587'))
        self.username=os.getenv('BABY_SMTP_USERNAME','').strip(); self.password=os.getenv('BABY_SMTP_PASSWORD',''); self.from_email=os.getenv('BABY_SMTP_FROM_EMAIL','').strip(); self.from_name=os.getenv('BABY_SMTP_FROM_NAME','Baby Investor').strip()
    def status(self):
        configured=all([self.enabled,self.host,self.port,self.username,self.password,self.from_email])
        return {'enabled':self.enabled,'configured':bool(configured),'host':self.host or None,'port':self.port,'from_name':self.from_name,'from_email_configured':bool(self.from_email),'credentials_present':bool(self.username and self.password)}
    def send(self,to_email,subject,body):
        if not self.enabled: raise RuntimeError('BABY_EMAIL_ENABLED is not ENABLED.')
        missing=[k for k,v in {'BABY_SMTP_HOST':self.host,'BABY_SMTP_USERNAME':self.username,'BABY_SMTP_PASSWORD':self.password,'BABY_SMTP_FROM_EMAIL':self.from_email}.items() if not v]
        if missing: raise RuntimeError('Missing email configuration: '+', '.join(missing))
        msg=EmailMessage(); msg['Subject']=subject; msg['From']=f'{self.from_name} <{self.from_email}>'; msg['To']=to_email; msg.set_content(body)
        if self.port==465:
            with smtplib.SMTP_SSL(self.host,self.port,timeout=20,context=ssl.create_default_context()) as smtp:smtp.login(self.username,self.password);smtp.send_message(msg)
        else:
            with smtplib.SMTP(self.host,self.port,timeout=20) as smtp:smtp.ehlo();smtp.starttls(context=ssl.create_default_context());smtp.ehlo();smtp.login(self.username,self.password);smtp.send_message(msg)

class SubscriberEmailService:
    def __init__(self,db_path='data/baby_ui.db',report_dir='data/ui_research',scanner_path='data/scans/unusual-volume_latest.json'):
        self.store=SubscriberStore(db_path); self.mailer=SMTPMailer(); self.report_dir=Path(report_dir); self.scanner_path=Path(scanner_path); self.verification_minutes=int(os.getenv('BABY_EMAIL_VERIFICATION_MINUTES','30'))
    def status(self): return {'status':'READY','smtp':self.mailer.status(),'verified_subscribers':len(self.store.verified()),'execution_authority':'NONE','real_money_execution':'DISABLED'}
    def subscribers(self): return {'status':'READY','subscribers':self.store.list()}
    def deliveries(self,limit=100): return {'status':'READY','deliveries':self.store.deliveries(limit)}
    def add_subscriber(self,email):
        normalized=self.store.normalize_email(email); existing=self.store.get_by_email(normalized)
        if existing and existing['status']=='VERIFIED': return {'status':'ALREADY_VERIFIED','subscriber':existing}
        code=f'{secrets.randbelow(1_000_000):06d}'; sub=self.store.create_pending(normalized,code,self.verification_minutes); subject='Verify your Baby Investor email alerts'
        body=f'''Baby Investor email verification\n\nYour verification code is: {code}\n\nThis code expires in {self.verification_minutes} minutes.\n\nGive this code to the Baby owner so they can finish verification inside the Baby Alerts page.\n\nVerifying this address only enables research/setup emails. It does not connect a brokerage account and cannot place trades.'''
        key=f"verification:{sub['id']}:{sub['updated_at']}"
        try:self.mailer.send(normalized,subject,body);self.store.record_delivery(sub['id'],normalized,None,'VERIFICATION',key,'SENT',subject)
        except Exception as exc:self.store.record_delivery(sub['id'],normalized,None,'VERIFICATION',key,'FAILED',subject,str(exc));raise
        return {'status':'PENDING_VERIFICATION','subscriber':sub}
    def resend(self,email): return self.add_subscriber(email)
    def verify(self,email,code):
        sub=self.store.verify(email,code); subject='Baby Investor email alerts verified'; body='Your email address is verified for Baby Investor research/setup alerts.\n\nFuture emails may include why Baby noticed a stock, relevant recent news, the deterministic setup, entry/invalidation/targets, and risks.\n\nResearch alerts only. No trade is placed by email.'; key=f"verified:{sub['id']}:{sub['verified_at']}"
        try:self.mailer.send(sub['email'],subject,body);self.store.record_delivery(sub['id'],sub['email'],None,'VERIFIED',key,'SENT',subject)
        except Exception as exc:self.store.record_delivery(sub['id'],sub['email'],None,'VERIFIED',key,'FAILED',subject,str(exc))
        return {'status':'VERIFIED','subscriber':sub}
    def remove(self,sid):
        r=self.store.remove(sid)
        if not r:raise ValueError('Subscriber not found.')
        return {'status':'REMOVED','subscriber':r}
    def _load_report(self,symbol):
        p=self.report_dir/f'{symbol.upper()}.json'
        try:return json.loads(p.read_text()) if p.exists() else {}
        except Exception:return {}
    def _scanner_candidate(self,symbol):
        try:
            d=json.loads(self.scanner_path.read_text()); rows=d.get('candidates') or d.get('results') or d.get('stocks') or []
            return next((r for r in rows if _upper(r.get('symbol') or r.get('ticker'))==symbol.upper()),{})
        except Exception:return {}
    @staticmethod
    def _company_news_terms(company):
        common={"inc","incorporated","corp","corporation","company","co","ltd","limited","plc","group","holdings","holding","the"}
        words=[x.lower() for x in re.findall(r"[A-Za-z0-9]+",str(company or ""))]
        return [x for x in words if len(x)>=4 and x not in common]

    @classmethod
    def _is_company_specific_headline(cls,item,symbol,company):
        headline=str((item or {}).get("headline") or (item or {}).get("title") or "").strip()
        if not headline:
            return False
        if re.search(rf"(?<![A-Za-z0-9]){re.escape(symbol.upper())}(?![A-Za-z0-9])",headline.upper()):
            return True
        low=headline.lower()
        return any(term in low for term in cls._company_news_terms(company))

    def _recent_news(self,symbol,company=None):
        try:
            from .alpaca_market import AlpacaMarketScreener
            r=AlpacaMarketScreener().news(symbols=[symbol.upper()],limit=10)
            rows=[x for x in (r.get("news") or []) if isinstance(x,dict)]
            return [x for x in rows if self._is_company_specific_headline(x,symbol,company)][:3]
        except Exception:
            return []
    @staticmethod
    def _proposal(decision):return (((decision or {}).get('proposal') or {}).get('payload') or {}).get('paper_proposal') or {}
    @classmethod
    def _state(cls,decision):
        payload=((decision or {}).get('proposal') or {}).get('payload') or {}; paper=payload.get('paper_proposal') or {}; state=paper.get('setup_status') or payload.get('setup_status') or paper.get('status') or decision.get('status') or 'UNKNOWN'; ready=bool(paper.get('eligible')) and _upper(paper.get('status'))=='ELIGIBLE'; return _upper(state),ready
    def _why_noticed(self,candidate,report,decision):
        b=[]; score=candidate.get('opportunity_score',candidate.get('score'))
        if score is not None:b.append(f'Scanner opportunity score: {score}.')
        for key,label,sfx in [('relative_volume','Relative volume','x'),('rvol','Relative volume','x'),('average_rvol_5d','Average 5-day relative volume','x'),('return_1d_pct','1-day return','%'),('change_pct','Price change','%')]:
            v=candidate.get(key)
            if v is not None and not any(label in x for x in b):b.append(f'{label}: {v}{sfx}.')
            if len(b)>=3:break
        setup=candidate.get('flow_type') or candidate.get('setup')
        if setup:b.append(f'Scanner setup/context: {setup}.')
        if len(b)<2:
            rs=((decision.get('research_decision') or {}).get('score')) or report.get('score'); conf=((decision.get('research_decision') or {}).get('confidence')) or report.get('confidence')
            if rs is not None:b.append(f'Baby research attractiveness score: {rs} (not a probability or buy signal).')
            if conf is not None:b.append(f'Research evidence confidence: {conf}%.')
        return (b or ["Baby's scanner and deterministic research pipeline kept this symbol as an active research candidate."])[:4]
    @staticmethod
    def _news_lines(news):
        if not news:return ["No significant company-specific catalyst was identified in Baby's configured news feed at alert time.","The setup alert is therefore based primarily on deterministic market/research evidence; event causality is NOT_ESTABLISHED."]
        lines=['Recent company news that may be relevant (headline timing does not establish price causality):']
        for item in news[:2]:
            h=str(item.get('headline') or '').strip(); src=str(item.get('source') or 'UNKNOWN').strip(); when=str(item.get('created_at') or item.get('published_at') or '').strip(); suffix=' · '.join(x for x in [src,when] if x)
            if h:lines.append(f'- {h}'+(f' ({suffix})' if suffix else ''))
        return lines
    def _build_setup_email(self,symbol,decision,previous_state):
        symbol=symbol.upper(); report=self._load_report(symbol); cand=self._scanner_candidate(symbol); paper=self._proposal(decision); state,_=self._state(decision); company=report.get('company_name') or cand.get('name') or cand.get('company_name') or symbol; why=self._why_noticed(cand,report,decision); news=self._recent_news(symbol,company); reason=paper.get('reason')
        if reason=='All deterministic paper-proposal gates passed.':reason=f'The deterministic setup is active ({state}) and all current proposal gates passed.'
        reason=reason or f"Baby's deterministic setup is currently {state}."; risk=paper.get('risk_level') or report.get('risk') or 'UNKNOWN'; subject=f'Baby — {symbol} setup ready for review'
        parts=['BABY — SETUP READY','',f'{symbol} — {company}',f"Current price: {_money(paper.get('quote_price'))}",'','WHY BABY NOTICED THIS STOCK',*[f'- {x}' for x in why],'','WHY IT MATTERS NOW',reason,f"State change: {previous_state or 'FIRST READY OBSERVATION'} -> {state}",'','RELEVANT NEWS / CATALYST',*self._news_lines(news),'','TRADE PLAN',f'Setup: {state}',f"Planned entry: {_money(paper.get('entry_price'))}",f"Invalidation: {_money(paper.get('invalidation'))}",f"Target 1: {_money(paper.get('target_1'))}",f"Target 2: {_money(paper.get('target_2'))}",f"R/R Target 1: {_rr(paper.get('rr_target_1'))}",f"R/R Target 2: {_rr(paper.get('rr_target_2'))}",'','MAIN RISK',f"Current Baby risk level: {risk}. The stored invalidation level is {_money(paper.get('invalidation'))}.",'','Research/setup alert only. No trade was placed.','Position size is intentionally omitted because each subscriber must make decisions using their own account and risk limits.','AI execution authority: NONE. Real-money execution: DISABLED.']
        return subject,'\n'.join(parts)
    def handle_candidate_decision(self,symbol,decision):
        symbol=symbol.upper(); state,ready=self._state(decision); old=self.store.candidate_state(symbol); prev_ready=bool(old and old.get('last_ready')); prev_state=old.get('last_state') if old else None; should=ready and not prev_ready; self.store.set_candidate_state(symbol,state,ready,False)
        if not should:return {'status':'NO_EMAIL','symbol':symbol,'state':state,'ready':ready,'previous_state':prev_state}
        subs=self.store.verified()
        if not subs:return {'status':'NO_VERIFIED_SUBSCRIBERS','symbol':symbol,'state':state,'ready':ready}
        subject,body=self._build_setup_email(symbol,decision,prev_state); transition=f"{prev_state or 'NONE'}->{state}:{iso()[:16]}"; sent=failed=0
        for sub in subs:
            key=f'setup-ready:{symbol}:{transition}'
            if self.store.delivery_exists(sub['id'],key):continue
            try:self.mailer.send(sub['email'],subject,body);self.store.record_delivery(sub['id'],sub['email'],symbol,'SETUP_READY',key,'SENT',subject);sent+=1
            except Exception as exc:self.store.record_delivery(sub['id'],sub['email'],symbol,'SETUP_READY',key,'FAILED',subject,str(exc));failed+=1
        self.store.set_candidate_state(symbol,state,ready,sent>0)
        return {'status':'EMAILED' if sent else 'DELIVERY_FAILED','symbol':symbol,'state':state,'sent':sent,'failed':failed}
