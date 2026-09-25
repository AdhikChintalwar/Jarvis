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

from .v155_intelligence import analyze as v155_analyze
from .v155_pipeline import V155PipelineStore
from .v155_email import choose_event as v155_choose_event, build_email as v155_build_email

from .email_branding import email_shell, verification_html, BABY_EMAIL_LOGO_PATH, BABY_EMAIL_LOGO_CID

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
            delivery_cols={r[1] for r in db.execute("PRAGMA table_info(email_deliveries)").fetchall()}
            if 'attempt_count' not in delivery_cols:
                db.execute("ALTER TABLE email_deliveries ADD COLUMN attempt_count INTEGER NOT NULL DEFAULT 1")
            if 'last_attempt_at' not in delivery_cols:
                db.execute("ALTER TABLE email_deliveries ADD COLUMN last_attempt_at TEXT")
            state_cols={r[1] for r in db.execute("PRAGMA table_info(candidate_alert_state)").fetchall()}
            if 'ready_episode' not in state_cols:
                db.execute("ALTER TABLE candidate_alert_state ADD COLUMN ready_episode INTEGER NOT NULL DEFAULT 0")
            db.commit()
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
    def observe_candidate_state(self,symbol,state,ready):
        symbol=symbol.upper(); now=iso()
        with self._db() as db:
            row=db.execute('SELECT * FROM candidate_alert_state WHERE symbol=?',(symbol,)).fetchone()
            prev_ready=bool(row and row['last_ready'])
            episode=int((row['ready_episode'] if row and 'ready_episode' in row.keys() else 0) or 0)
            if ready and not prev_ready:
                episode+=1
            last_alert=row['last_alert_at'] if row else None
            sql='INSERT INTO candidate_alert_state(symbol,last_state,last_ready,updated_at,last_alert_at,ready_episode) VALUES(?,?,?,?,?,?) ON CONFLICT(symbol) DO UPDATE SET last_state=excluded.last_state,last_ready=excluded.last_ready,updated_at=excluded.updated_at,ready_episode=excluded.ready_episode'
            db.execute(sql,(symbol,state,1 if ready else 0,now,last_alert,episode))
            db.commit()
        return {'previous_ready':prev_ready,'previous_state':row['last_state'] if row else None,'ready_episode':episode}

    def mark_candidate_alerted(self,symbol):
        now=iso()
        with self._db() as db:
            db.execute('UPDATE candidate_alert_state SET last_alert_at=?,updated_at=? WHERE symbol=?',(now,now,symbol.upper()))
            db.commit()

    def delivery_row(self,sid,key):
        with self._db() as db:
            r=db.execute('SELECT * FROM email_deliveries WHERE subscriber_id=? AND dedupe_key=? LIMIT 1',(int(sid),key)).fetchone()
        return dict(r) if r else None

    def delivery_exists(self,sid,key):
        r=self.delivery_row(sid,key)
        return bool(r and str(r.get('delivery_status') or '').upper()=='SENT')

    def retry_allowed(self,sid,key,cooldown_seconds=300,max_attempts=3):
        r=self.delivery_row(sid,key)
        if not r:return True,'FIRST_ATTEMPT'
        if str(r.get('delivery_status') or '').upper()=='SENT':return False,'ALREADY_SENT'
        attempts=int(r.get('attempt_count') or 1)
        if attempts>=max(1,int(max_attempts)):return False,'MAX_ATTEMPTS'
        last=r.get('last_attempt_at') or r.get('created_at')
        try:
            dt=datetime.fromisoformat(str(last).replace('Z','+00:00'))
            if dt.tzinfo is None:dt=dt.replace(tzinfo=timezone.utc)
            age=(utcnow()-dt.astimezone(timezone.utc)).total_seconds()
            if age<max(0,int(cooldown_seconds)):return False,'RETRY_COOLDOWN'
        except Exception:
            pass
        return True,'RETRY'

    def record_delivery(self,sid,email,symbol,event_type,key,status,subject,error=None):
        now=iso(); status=_upper(status)
        with self._db() as db:
            existing=db.execute(
                'SELECT id,delivery_status,attempt_count,sent_at FROM email_deliveries WHERE subscriber_id=? AND dedupe_key=? LIMIT 1',
                (int(sid),key)
            ).fetchone()
            if not existing:
                sql='INSERT INTO email_deliveries(subscriber_id,email,symbol,event_type,dedupe_key,delivery_status,subject,error,created_at,sent_at,attempt_count,last_attempt_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)'
                db.execute(
                    sql,
                    (sid,email,symbol,event_type,key,status,subject,error,now,now if status=='SENT' else None,1,now)
                )
            elif _upper(existing['delivery_status'])!='SENT':
                attempts=int(existing['attempt_count'] or 1)+1
                sql='UPDATE email_deliveries SET email=?,symbol=?,event_type=?,delivery_status=?,subject=?,error=?,sent_at=CASE WHEN ?="SENT" THEN ? ELSE sent_at END,attempt_count=?,last_attempt_at=? WHERE id=?'
                db.execute(
                    sql,
                    (email,symbol,event_type,status,subject,error,status,now,attempts,now,existing['id'])
                )
            db.commit()

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
    def send(self,to_email,subject,body,html_body=None):
        if not self.enabled:
            raise RuntimeError('BABY_EMAIL_ENABLED is not ENABLED.')
        missing=[k for k,v in {
            'BABY_SMTP_HOST':self.host,
            'BABY_SMTP_USERNAME':self.username,
            'BABY_SMTP_PASSWORD':self.password,
            'BABY_SMTP_FROM_EMAIL':self.from_email,
        }.items() if not v]
        if missing:
            raise RuntimeError('Missing email configuration: '+', '.join(missing))

        msg=EmailMessage()
        msg['Subject']=subject
        msg['From']=f'{self.from_name} <{self.from_email}>'
        msg['To']=to_email
        msg.set_content(body)

        if html_body:
            msg.add_alternative(html_body,subtype='html')
            logo_path=Path(BABY_EMAIL_LOGO_PATH)
            if logo_path.exists():
                html_part=msg.get_payload()[-1]
                html_part.add_related(
                    logo_path.read_bytes(),
                    maintype='image',
                    subtype='png',
                    cid=f'<{BABY_EMAIL_LOGO_CID}>',
                    disposition='inline',
                    filename='baby-logo.png',
                )

        if self.port==465:
            with smtplib.SMTP_SSL(self.host,self.port,timeout=20,context=ssl.create_default_context()) as smtp:
                smtp.login(self.username,self.password)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(self.host,self.port,timeout=20) as smtp:
                smtp.ehlo()
                smtp.starttls(context=ssl.create_default_context())
                smtp.ehlo()
                smtp.login(self.username,self.password)
                smtp.send_message(msg)

class SubscriberEmailService:
    def __init__(self,db_path='data/baby_ui.db',report_dir='data/ui_research',scanner_path='data/scans/unusual-volume_latest.json'):
        self.store=SubscriberStore(db_path); self.mailer=SMTPMailer(); self.report_dir=Path(report_dir); self.scanner_path=Path(scanner_path); self.verification_minutes=int(os.getenv('BABY_EMAIL_VERIFICATION_MINUTES','30')); self.v155_store=V155PipelineStore(db_path)
        self.retry_cooldown_seconds=max(0,int(os.getenv('BABY_EMAIL_RETRY_COOLDOWN_SECONDS','300')))
        self.max_delivery_attempts=max(1,min(int(os.getenv('BABY_EMAIL_MAX_ATTEMPTS','3')),10))
    def status(self): return {'status':'READY','smtp':self.mailer.status(),'verified_subscribers':len(self.store.verified()),'execution_authority':'NONE','real_money_execution':'DISABLED'}
    def subscribers(self): return {'status':'READY','subscribers':self.store.list()}
    def deliveries(self,limit=100): return {'status':'READY','deliveries':self.store.deliveries(limit)}
    def add_subscriber(self,email):
        normalized=self.store.normalize_email(email); existing=self.store.get_by_email(normalized)
        if existing and existing['status']=='VERIFIED': return {'status':'ALREADY_VERIFIED','subscriber':existing}
        code=f'{secrets.randbelow(1_000_000):06d}'; sub=self.store.create_pending(normalized,code,self.verification_minutes); subject='Verify your Baby Investor email alerts'
        body=f'''Baby Investor email verification\n\nYour verification code is: {code}\n\nThis code expires in {self.verification_minutes} minutes.\n\nGive this code to the Baby owner so they can finish verification inside the Baby Alerts page.\n\nVerifying this address only enables research/setup emails. It does not connect a brokerage account and cannot place trades.'''
        key=f"verification:{sub['id']}:{sub['updated_at']}"
        html_body=verification_html(code,self.verification_minutes)
        try:self.mailer.send(normalized,subject,body,html_body);self.store.record_delivery(sub['id'],normalized,None,'VERIFICATION',key,'SENT',subject)
        except Exception as exc:self.store.record_delivery(sub['id'],normalized,None,'VERIFICATION',key,'FAILED',subject,str(exc));raise
        return {'status':'PENDING_VERIFICATION','subscriber':sub}
    def resend(self,email): return self.add_subscriber(email)
    def verify(self,email,code):
        sub=self.store.verify(email,code); subject='Baby Investor email alerts verified'; body='Your email address is verified for Baby Investor research/setup alerts.\n\nFuture emails may include why Baby noticed a stock, relevant recent news, the deterministic setup, entry/invalidation/targets, and risks.\n\nResearch alerts only. No trade is placed by email.'; key=f"verified:{sub['id']}:{sub['verified_at']}"
        html_body=email_shell(
            'Alerts Verified',
            'Baby research alerts are enabled.',
            '<h1 style="font-size:26px;margin:12px 0;color:#102a43">Research alerts enabled</h1>'
            '<p style="color:#526d82;line-height:1.65">Your email is verified for Baby research and setup alerts.</p>'
            '<div style="margin:20px 0;padding:16px;border:1px solid #cbd9e6;background:#f4f8fc;border-radius:14px">'
            '<div style="color:#1769aa;font-size:11px;letter-spacing:.12em;font-weight:800">WHAT YOU MAY RECEIVE</div>'
            '<div style="margin-top:8px;color:#486581;line-height:1.7">Why Baby noticed a stock, what changed, company-specific news, trade-plan levels, risk context, and data freshness.</div>'
            '</div>'
            '<div style="margin:20px 0;padding:16px;border:1px solid #d2deea;background:#f7fafd;border-radius:14px">'
            '<div style="color:#1769aa;font-size:11px;letter-spacing:.12em;font-weight:800">AUTHORITY</div>'
            '<div style="margin-top:8px;color:#102a43;line-height:1.7">AI execution authority: NONE<br>Real-money execution: DISABLED</div>'
            '</div>'
        )
        try:self.mailer.send(sub['email'],subject,body,html_body);self.store.record_delivery(sub['id'],sub['email'],None,'VERIFIED',key,'SENT',subject)
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
    @staticmethod
    def _html_escape(v):
        from html import escape
        return escape("" if v is None else str(v))

    @classmethod
    def _setup_html(cls,symbol,company,state,reason,previous_state,why,news,paper,risk):
        e=cls._html_escape
        provider=paper.get('quote_provider') or paper.get('provider') or paper.get('execution_quote_provider') or 'UNKNOWN'
        age=paper.get('quote_age_seconds')
        if age is None:
            age=paper.get('age_seconds')
        quote_asof=paper.get('quote_asof') or paper.get('asof') or paper.get('quote_timestamp')
        freshness=f"{age:.0f} seconds old" if isinstance(age,(int,float)) else 'UNKNOWN'
        transition=f"{previous_state or 'FIRST READY OBSERVATION'} -> {state}"

        why_html=''.join(f'<li style="margin:0 0 8px">{e(x)}</li>' for x in why)

        if news:
            chunks=[]
            for item in news[:2]:
                headline=str(item.get('headline') or item.get('title') or '').strip()
                source=str(item.get('source') or 'UNKNOWN').strip()
                when=str(item.get('created_at') or item.get('published_at') or 'time unknown').strip()
                chunks.append(
                    '<div style="padding:10px 0;border-bottom:1px solid #d7e3ef">'
                    f'<div style="color:#102a43;font-size:13px;line-height:1.55">{e(headline)}</div>'
                    f'<div style="color:#627d98;font-size:11px;margin-top:4px">{e(source)} · {e(when)}</div>'
                    '</div>'
                )
            news_html=''.join(chunks)
            catalyst_note='Headline timing does not establish price causality. Causality: NOT_ESTABLISHED.'
        else:
            news_html="<div style='color:#526d82;font-size:13px;line-height:1.6'>No significant company-specific catalyst was identified in Baby's configured news feed at alert time.</div>"
            catalyst_note='The setup is based primarily on deterministic market/research evidence. Causality: NOT_ESTABLISHED.'

        rows=[
            ('Current price',_money(paper.get('quote_price'))),
            ('Planned entry',_money(paper.get('entry_price'))),
            ('Invalidation',_money(paper.get('invalidation'))),
            ('Target 1',_money(paper.get('target_1'))),
            ('Target 2',_money(paper.get('target_2'))),
            ('R/R Target 1',_rr(paper.get('rr_target_1'))),
            ('R/R Target 2',_rr(paper.get('rr_target_2'))),
        ]
        table_rows=''
        for i,(label,value) in enumerate(rows):
            border='border-bottom:1px solid #d7e3ef;' if i < len(rows)-1 else ''
            table_rows+=(
                '<tr>'
                f'<td style="padding:9px 0;{border}color:#627d98;font-size:13px">{e(label)}</td>'
                f'<td align="right" style="padding:9px 0;{border}color:#102a43;font-size:13px;font-weight:700">{e(value)}</td>'
                '</tr>'
            )

        body=(
            f'<h1 style="font-size:28px;line-height:1.25;margin:14px 0 4px;color:#102a43">{e(symbol)} — {e(company)}</h1>'
            f'<div style="color:#627d98;font-size:13px;margin-bottom:22px">Setup ready for review</div>'
            '<div style="padding:16px;border:1px solid #bfd3e5;background:#f4f8fc;border-radius:14px;margin:18px 0">'
            '<div style="color:#1769aa;font-size:11px;font-weight:800;letter-spacing:.12em">SETUP STATUS</div>'
            f'<div style="color:#102a43;font-size:21px;font-weight:800;margin-top:7px">{e(state)}</div>'
            f'<div style="color:#627d98;font-size:13px;line-height:1.6;margin-top:8px">{e(reason)}</div>'
            '</div>'
            '<div style="margin:24px 0">'
            '<div style="color:#1769aa;font-size:11px;font-weight:800;letter-spacing:.12em;margin-bottom:10px">WHY BABY NOTICED THIS STOCK</div>'
            f'<ul style="margin:0;padding-left:20px;color:#486581;font-size:13px;line-height:1.65">{why_html}</ul>'
            '</div>'
            '<div style="margin:24px 0">'
            '<div style="color:#1769aa;font-size:11px;font-weight:800;letter-spacing:.12em;margin-bottom:8px">WHAT CHANGED / WHY NOW</div>'
            f'<div style="color:#486581;font-size:13px;line-height:1.65">{e(reason)}</div>'
            f'<div style="color:#627d98;font-size:12px;margin-top:8px">State change: {e(transition)}</div>'
            '</div>'
            '<div style="margin:24px 0">'
            '<div style="color:#1769aa;font-size:11px;font-weight:800;letter-spacing:.12em;margin-bottom:8px">TRADE PLAN</div>'
            f'<table width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse">{table_rows}</table>'
            '</div>'
            '<div style="margin:24px 0">'
            '<div style="color:#1769aa;font-size:11px;font-weight:800;letter-spacing:.12em;margin-bottom:8px">MAIN RISK</div>'
            f'<div style="color:#486581;font-size:13px;line-height:1.65">Current Baby risk level: <b style="color:#102a43">{e(risk)}</b>. Stored invalidation: <b style="color:#102a43">{e(_money(paper.get("invalidation")))}</b>.</div>'
            '</div>'
            '<div style="margin:24px 0">'
            '<div style="color:#1769aa;font-size:11px;font-weight:800;letter-spacing:.12em;margin-bottom:8px">CATALYSTS & COMPANY NEWS</div>'
            f'{news_html}'
            f'<div style="color:#627d98;font-size:11px;line-height:1.55;margin-top:10px">{e(catalyst_note)}</div>'
            '</div>'
            '<div style="margin:24px 0;padding:14px;border:1px solid #d2deea;background:#f7fafd;border-radius:12px">'
            '<div style="color:#1769aa;font-size:11px;font-weight:800;letter-spacing:.12em;margin-bottom:8px">DATA FRESHNESS</div>'
            f'<div style="color:#526d82;font-size:12px;line-height:1.65">Quote provider: {e(provider)}<br>Quote age: {e(freshness)}<br>Quote as-of: {e(quote_asof or "UNKNOWN")}</div>'
            '</div>'
            '<div style="margin-top:22px;padding:13px;border:1px solid #d2deea;background:#f7fafd;border-radius:11px;color:#526d82;font-size:12px;line-height:1.65">'
            'Baby determines the trade plan only. Quantity is intentionally omitted; you choose the Alpaca PAPER quantity manually.'
            '</div>'
        )
        return email_shell('Setup Ready',f'{symbol} is ready for review in Baby.',body)

    def _build_setup_email(self,symbol,decision,previous_state):
        symbol=symbol.upper(); report=self._load_report(symbol); cand=self._scanner_candidate(symbol); paper=self._proposal(decision); state,_=self._state(decision); company=report.get('company_name') or cand.get('name') or cand.get('company_name') or symbol; why=self._why_noticed(cand,report,decision); news=self._recent_news(symbol,company); reason=paper.get('reason')
        if reason=='All deterministic paper-proposal gates passed.':reason=f'The deterministic setup is active ({state}) and all current proposal gates passed.'
        reason=reason or f"Baby's deterministic setup is currently {state}."; risk=paper.get('risk_level') or report.get('risk') or 'UNKNOWN'; subject=f'Baby — {symbol} ({company}) — setup ready for review'
        parts=['BABY — SETUP READY','',f'{symbol} — {company}',f"Current price: {_money(paper.get('quote_price'))}",'','WHY BABY NOTICED THIS STOCK',*[f'- {x}' for x in why],'','WHY IT MATTERS NOW',reason,f"State change: {previous_state or 'FIRST READY OBSERVATION'} -> {state}",'','RELEVANT NEWS / CATALYST',*self._news_lines(news),'','TRADE PLAN',f'Setup: {state}',f"Planned entry: {_money(paper.get('entry_price'))}",f"Invalidation: {_money(paper.get('invalidation'))}",f"Target 1: {_money(paper.get('target_1'))}",f"Target 2: {_money(paper.get('target_2'))}",f"R/R Target 1: {_rr(paper.get('rr_target_1'))}",f"R/R Target 2: {_rr(paper.get('rr_target_2'))}",'','MAIN RISK',f"Current Baby risk level: {risk}. The stored invalidation level is {_money(paper.get('invalidation'))}.",'','Research/setup alert only. No trade was placed.','Position size is intentionally omitted because each subscriber must make decisions using their own account and risk limits.','AI execution authority: NONE. Real-money execution: DISABLED.']
        text_body='\n'.join(parts)
        html_body=self._setup_html(symbol,company,state,reason,previous_state,why,news,paper,risk)
        return subject,text_body,html_body
    def _v155_record_and_maybe_email(self,symbol,decision):
        symbol=symbol.upper()
        report=self._load_report(symbol)
        cand=self._scanner_candidate(symbol)
        previous=self.v155_store.latest(symbol)
        intel=v155_analyze(symbol,cand,report,decision)
        self.v155_store.record(intel)
        event=v155_choose_event(intel,previous)
        if not event:return {"event":None,"intelligence":intel.as_dict()}

        company=report.get('company_name') or cand.get('company_name') or cand.get('name') or symbol

        # CATALYST_UPDATE must be genuinely company-specific.
        # Generic market/news headlines are not subscriber-worthy merely
        # because the source/event classifier rated them MEDIUM/HIGH.
        if event=='CATALYST_UPDATE':
            headline=(intel.catalyst.headline or '').strip()
            if not self._is_company_specific_headline(
                {'headline': headline},
                symbol,
                company,
            ):
                return {
                    "event":None,
                    "suppressed_event":"CATALYST_UPDATE",
                    "reason":"CATALYST_NOT_COMPANY_SPECIFIC",
                    "intelligence":intel.as_dict(),
                }

        if not self.v155_store.should_email(symbol,event,intel.fingerprint):return {"event":"DEDUPED","intelligence":intel.as_dict()}
        context=(report.get('market_context') or report.get('v156_market_context') or report.get('context') or {})
        paper=self._proposal(decision)
        subject,text_body,html_body=v155_build_email(intel,event,context,company,paper)
        sent=failed=0
        for sub in self.store.verified():
            key=f"v155:{event}:{symbol}:{intel.fingerprint}"
            try:
                self.mailer.send(sub["email"],subject,text_body,html_body)
                self.store.record_delivery(sub["id"],sub["email"],symbol,event,key,"SENT",subject)
                sent+=1
            except Exception as exc:
                self.store.record_delivery(sub["id"],sub["email"],symbol,event,key,"FAILED",subject,str(exc))
                failed+=1
        if sent:self.v155_store.mark_email(symbol,event,intel.fingerprint)
        return {"event":event,"sent":sent,"failed":failed,"intelligence":intel.as_dict()}
    def handle_candidate_decision(self,symbol,decision):
        v155=self._v155_record_and_maybe_email(symbol,decision)
        symbol=symbol.upper(); state,ready=self._state(decision)
        observed=self.store.observe_candidate_state(symbol,state,ready)
        prev_state=observed.get('previous_state')
        episode=int(observed.get('ready_episode') or 0)

        if not ready:
            return {
                'status':'NO_EMAIL','symbol':symbol,'state':state,'ready':ready,
                'previous_state':prev_state,'v155':v155
            }

        subs=self.store.verified()
        if not subs:
            return {
                'status':'NO_VERIFIED_SUBSCRIBERS','symbol':symbol,'state':state,
                'ready':ready,'ready_episode':episode,'v155':v155
            }

        subject,body,html_body=self._build_setup_email(symbol,decision,prev_state)
        key=f'setup-ready:{symbol}:episode:{episode}:{state}'
        sent=failed=deduped=cooldown=maxed=0

        for sub in subs:
            allowed,reason=self.store.retry_allowed(
                sub['id'],key,self.retry_cooldown_seconds,self.max_delivery_attempts
            )
            if not allowed:
                if reason=='ALREADY_SENT':deduped+=1
                elif reason=='RETRY_COOLDOWN':cooldown+=1
                elif reason=='MAX_ATTEMPTS':maxed+=1
                continue
            try:
                self.mailer.send(sub['email'],subject,body,html_body)
                self.store.record_delivery(
                    sub['id'],sub['email'],symbol,'SETUP_READY',key,'SENT',subject
                )
                sent+=1
            except Exception as exc:
                self.store.record_delivery(
                    sub['id'],sub['email'],symbol,'SETUP_READY',key,'FAILED',subject,str(exc)
                )
                failed+=1

        if sent:self.store.mark_candidate_alerted(symbol)

        status=(
            'EMAILED' if sent else
            'DELIVERY_FAILED' if failed else
            'RETRY_COOLDOWN' if cooldown else
            'MAX_ATTEMPTS' if maxed else
            'DEDUPED'
        )
        return {
            'status':status,'symbol':symbol,'state':state,'ready':ready,
            'ready_episode':episode,'dedupe_key':key,'sent':sent,'failed':failed,
            'deduped':deduped,'retry_cooldown':cooldown,
            'max_attempts_reached':maxed,'v155':v155,
        }
