from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Callable

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse

try:
    from webauthn import (
        generate_registration_options,
        verify_registration_response,
        generate_authentication_options,
        verify_authentication_response,
        options_to_json,
    )
    from webauthn.helpers.structs import (
        AuthenticatorSelectionCriteria,
        ResidentKeyRequirement,
        UserVerificationRequirement,
        PublicKeyCredentialDescriptor,
    )
    WEBAUTHN_AVAILABLE = True
except Exception:
    WEBAUTHN_AVAILABLE = False

router = APIRouter(prefix="/quick", tags=["Baby Quick V15.16"])


def _now():
    return datetime.now(timezone.utc)


def _iso(dt=None):
    return (dt or _now()).isoformat()


def _b64e(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _b64d(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _f(v):
    try:
        return float(v)
    except Exception:
        return None


class QuickRuntime:
    proposal_getter: Callable | None = None
    quote_getter: Callable | None = None
    account_getter: Callable | None = None
    order_submitter: Callable | None = None
    ledger: Any = None
    notifier: Any = None


runtime = QuickRuntime()


def configure_quick_runtime(**kwargs):
    for key, value in kwargs.items():
        if hasattr(runtime, key):
            setattr(runtime, key, value)


class QuickStore:
    def __init__(self, db_path=None):
        self.db_path = Path(
            db_path
            or os.getenv("BABY_UI_DB")
            or os.getenv("BABY_UI_DB_PATH")
            or "data/baby_ui.db"
        )
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure()

    def db(self):
        db = sqlite3.connect(self.db_path)
        db.row_factory = sqlite3.Row
        return db

    def _ensure(self):
        with self.db() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS v1516_passkeys(
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  credential_id TEXT NOT NULL UNIQUE,
                  public_key_b64 TEXT NOT NULL,
                  sign_count INTEGER NOT NULL DEFAULT 0,
                  label TEXT,
                  created_at TEXT NOT NULL,
                  last_used_at TEXT
                );
                CREATE TABLE IF NOT EXISTS v1516_webauthn_challenges(
                  id TEXT PRIMARY KEY,
                  kind TEXT NOT NULL,
                  challenge_b64 TEXT NOT NULL,
                  bootstrap_ok INTEGER NOT NULL DEFAULT 0,
                  created_at TEXT NOT NULL,
                  expires_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS v1516_quick_tokens(
                  nonce TEXT PRIMARY KEY,
                  symbol TEXT NOT NULL,
                  ready_episode INTEGER NOT NULL,
                  purpose TEXT NOT NULL,
                  expires_at TEXT NOT NULL,
                  consumed_at TEXT,
                  created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS v1516_quick_audit(
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  action TEXT NOT NULL,
                  symbol TEXT,
                  ready_episode INTEGER,
                  result TEXT NOT NULL,
                  details_json TEXT NOT NULL DEFAULT '{}',
                  created_at TEXT NOT NULL
                );
                """
            )
            db.commit()

    def credential_count(self):
        with self.db() as db:
            return int(db.execute("SELECT COUNT(*) n FROM v1516_passkeys").fetchone()["n"])

    def credentials(self):
        with self.db() as db:
            return [dict(r) for r in db.execute("SELECT * FROM v1516_passkeys ORDER BY id")]

    def challenge_put(self, kind, challenge: bytes, bootstrap_ok=False):
        challenge_id = secrets.token_urlsafe(24)
        now = _now()
        expires = now + timedelta(minutes=5)
        with self.db() as db:
            db.execute(
                "INSERT INTO v1516_webauthn_challenges(id,kind,challenge_b64,bootstrap_ok,created_at,expires_at) VALUES(?,?,?,?,?,?)",
                (challenge_id, kind, _b64e(challenge), 1 if bootstrap_ok else 0, _iso(now), _iso(expires)),
            )
            db.commit()
        return challenge_id

    def challenge_pop(self, challenge_id, kind):
        with self.db() as db:
            row = db.execute(
                "SELECT * FROM v1516_webauthn_challenges WHERE id=? AND kind=?",
                (challenge_id, kind),
            ).fetchone()
            if not row:
                return None
            db.execute("DELETE FROM v1516_webauthn_challenges WHERE id=?", (challenge_id,))
            db.commit()
        result = dict(row)
        if datetime.fromisoformat(result["expires_at"]) < _now():
            return None
        return result

    def add_credential(self, credential_id: bytes, public_key: bytes, sign_count: int):
        cid = _b64e(credential_id)
        with self.db() as db:
            db.execute(
                "INSERT OR REPLACE INTO v1516_passkeys(credential_id,public_key_b64,sign_count,label,created_at,last_used_at) VALUES(?,?,?,?,COALESCE((SELECT created_at FROM v1516_passkeys WHERE credential_id=?),?),?)",
                (cid, _b64e(public_key), int(sign_count), "Primary passkey", cid, _iso(), _iso()),
            )
            db.commit()

    def update_sign_count(self, credential_id, sign_count):
        with self.db() as db:
            db.execute(
                "UPDATE v1516_passkeys SET sign_count=?,last_used_at=? WHERE credential_id=?",
                (int(sign_count), _iso(), credential_id),
            )
            db.commit()

    def audit(self, action, result, symbol=None, episode=None, details=None):
        with self.db() as db:
            db.execute(
                "INSERT INTO v1516_quick_audit(action,symbol,ready_episode,result,details_json,created_at) VALUES(?,?,?,?,?,?)",
                (action, symbol, episode, result, json.dumps(details or {}, default=str), _iso()),
            )
            db.commit()


store = QuickStore()


def _secret(name):
    value = (os.getenv(name) or "").strip()
    if len(value) < 32:
        raise RuntimeError(f"{name} must be at least 32 characters")
    return value.encode()


def make_session():
    expires = int((_now() + timedelta(hours=12)).timestamp())
    nonce = secrets.token_urlsafe(18)
    body = f"{expires}.{nonce}"
    sig = _b64e(hmac.new(_secret("BABY_QUICK_SESSION_SECRET"), body.encode(), hashlib.sha256).digest())
    return f"{body}.{sig}"


def session_ok(token):
    try:
        exp_s, nonce, sig = token.split(".", 2)
        body = f"{exp_s}.{nonce}"
        expected = _b64e(hmac.new(_secret("BABY_QUICK_SESSION_SECRET"), body.encode(), hashlib.sha256).digest())
        return hmac.compare_digest(sig, expected) and int(exp_s) >= int(_now().timestamp())
    except Exception:
        return False


def require_session(request: Request):
    if not session_ok(request.cookies.get("baby_quick_session") or ""):
        raise HTTPException(401, "Passkey authentication required.")


def issue_setup_token(symbol, episode, ttl_minutes=15):
    symbol = symbol.upper()
    nonce = secrets.token_urlsafe(20)
    expires = _now() + timedelta(minutes=ttl_minutes)
    payload = {"s": symbol, "e": int(episode), "x": int(expires.timestamp()), "n": nonce}
    raw = _b64e(json.dumps(payload, separators=(",", ":")).encode())
    sig = _b64e(hmac.new(_secret("BABY_QUICK_TOKEN_SECRET"), raw.encode(), hashlib.sha256).digest())
    with store.db() as db:
        db.execute(
            "INSERT INTO v1516_quick_tokens(nonce,symbol,ready_episode,purpose,expires_at,created_at) VALUES(?,?,?,?,?,?)",
            (nonce, symbol, int(episode), "review", _iso(expires), _iso()),
        )
        db.commit()
    return f"{raw}.{sig}"


def verify_setup_token(token):
    try:
        raw, sig = token.split(".", 1)
        expected = _b64e(hmac.new(_secret("BABY_QUICK_TOKEN_SECRET"), raw.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, expected):
            return None
        payload = json.loads(_b64d(raw))
        if int(payload["x"]) < int(_now().timestamp()):
            return None
        with store.db() as db:
            row = db.execute("SELECT * FROM v1516_quick_tokens WHERE nonce=?", (payload["n"],)).fetchone()
            if not row or row["consumed_at"]:
                return None
        return payload
    except Exception:
        return None


def _equity(account):
    for key in ("equity", "portfolio_value", "account_equity"):
        value = _f((account or {}).get(key))
        if value and value > 0:
            return value
    return None


def _price(quote):
    quote = quote or {}
    for key in ("price", "last", "last_price", "mid", "quote_price"):
        value = _f(quote.get(key))
        if value and value > 0:
            return value
    bid = _f(quote.get("bid_price") or quote.get("bid"))
    ask = _f(quote.get("ask_price") or quote.get("ask"))
    if bid and ask:
        return (bid + ask) / 2
    return ask or bid


def _trade_count():
    today = _now().date().isoformat()
    with store.db() as db:
        row = db.execute("SELECT new_entries FROM v1515_daily_guard WHERE trade_date=?", (today,)).fetchone()
        return int(row["new_entries"]) if row else 0


def _increment_trade(equity):
    today = _now().date().isoformat()
    with store.db() as db:
        db.execute(
            "INSERT INTO v1515_daily_guard(trade_date,new_entries,starting_equity,last_updated_at) VALUES(?,1,?,?) ON CONFLICT(trade_date) DO UPDATE SET new_entries=new_entries+1,last_updated_at=excluded.last_updated_at",
            (today, equity, _iso()),
        )
        db.commit()


def _size(equity, price, stop):
    max_alloc = float(os.getenv("BABY_PAPER_MAX_ALLOCATION_PCT", "0.20"))
    max_risk = float(os.getenv("BABY_PAPER_MAX_PORTFOLIO_RISK_PCT", "0.01"))
    qty = int((equity * max_alloc) // price)
    if stop and 0 < stop < price:
        qty = min(qty, int((equity * max_risk) // (price - stop)))
    return max(0, qty)


def dashboard():
    with store.db() as db:
        pending = [dict(r) for r in db.execute(
            """
            SELECT fv.symbol,fv.ready_episode,fv.t0,fv.entry,fv.invalidation,fv.target1,fv.target2,
                   fv.quote_price,fv.paper_outcome,r.state,r.readiness_potential
            FROM v1511_forward_validation fv
            JOIN v1511_readiness r ON r.symbol=fv.symbol
            JOIN candidate_alert_state c ON c.symbol=fv.symbol AND c.ready_episode=fv.ready_episode
            WHERE r.state='SETUP_READY' AND c.last_ready=1 AND fv.alpaca_order_id IS NULL
            ORDER BY fv.t0 DESC LIMIT 25
            """
        )]
        positions = [dict(r) for r in db.execute(
            """
            SELECT symbol,ready_episode,fill_price,quantity,invalidation,target1,target2,paper_outcome,alpaca_order_id
            FROM v1511_forward_validation
            WHERE filled=1 AND quantity>0 AND paper_outcome='OPEN'
            ORDER BY first_fill_at DESC
            """
        )]
    return {
        "pending": pending,
        "positions": positions,
        "trades_today": _trade_count(),
        "max_trades": int(os.getenv("BABY_PAPER_MAX_NEW_TRADES_PER_DAY", "3")),
        "real_money_execution": "DISABLED",
    }


def _pending(symbol, episode):
    with store.db() as db:
        row = db.execute(
            """
            SELECT fv.* FROM v1511_forward_validation fv
            JOIN v1511_readiness rd ON rd.symbol=fv.symbol AND rd.state='SETUP_READY'
            JOIN candidate_alert_state c ON c.symbol=fv.symbol AND c.last_ready=1 AND c.ready_episode=fv.ready_episode
            WHERE fv.symbol=? AND fv.ready_episode=? AND fv.alpaca_order_id IS NULL LIMIT 1
            """,
            (symbol.upper(), int(episode)),
        ).fetchone()
        return dict(row) if row else None


def approve_existing(symbol, episode):
    max_trades = int(os.getenv("BABY_PAPER_MAX_NEW_TRADES_PER_DAY", "3"))
    if _trade_count() >= max_trades:
        raise HTTPException(409, "Daily PAPER trade limit reached. Setup remains tracked.")
    row = _pending(symbol, episode)
    if not row:
        raise HTTPException(409, "Setup is no longer a current pending SETUP_READY episode.")
    if not all([runtime.proposal_getter, runtime.quote_getter, runtime.account_getter, runtime.order_submitter, runtime.ledger]):
        raise HTTPException(503, "Quick execution runtime is not configured.")
    proposal = runtime.proposal_getter(symbol)
    if not (proposal.get("eligible") and str(proposal.get("status") or "").upper() == "ELIGIBLE"):
        raise HTTPException(409, proposal.get("reason") or "Setup no longer eligible.")
    quote = runtime.quote_getter(symbol)
    px = _price(quote)
    account = runtime.account_getter()
    equity = _equity(account)
    if not px or not equity:
        raise HTTPException(409, "Fresh quote/account equity unavailable.")
    stop = _f(proposal.get("invalidation") or proposal.get("stop") or row.get("invalidation"))
    qty = _size(equity, px, stop)
    if qty <= 0:
        raise HTTPException(409, "Risk sizing produced zero quantity.")
    order = runtime.order_submitter(
        symbol=symbol.upper(), side="BUY", quantity=qty, order_type="MARKET",
        confirmation="EXECUTE ALPACA PAPER",
        client_order_id=f"baby-quick-{symbol.lower()}-{int(episode)}",
    )
    order_id = order.get("id") or order.get("order_id")
    if not order_id:
        store.audit("APPROVE", "UNKNOWN", symbol, episode, order)
        raise HTTPException(503, "Broker response missing order id; manual reconciliation required.")
    runtime.ledger.attach_order(symbol, int(episode), order, qty)
    _increment_trade(equity)
    store.audit("APPROVE", "SUBMITTED", symbol, episode, {"qty": qty, "order_id": order_id})
    return {
        "status": "SUBMITTED", "symbol": symbol.upper(), "episode": int(episode), "quantity": qty,
        "order_id": order_id, "environment": "ALPACA_PAPER", "real_money_execution": "DISABLED",
    }


def close_existing(symbol, episode):
    with store.db() as db:
        row = db.execute(
            "SELECT * FROM v1511_forward_validation WHERE symbol=? AND ready_episode=? AND filled=1 AND quantity>0 AND paper_outcome='OPEN' LIMIT 1",
            (symbol.upper(), int(episode)),
        ).fetchone()
    if not row:
        raise HTTPException(409, "No open tracked PAPER position for this episode.")
    row = dict(row)
    order = runtime.order_submitter(
        symbol=symbol.upper(), side="SELL", quantity=float(row["quantity"]), order_type="MARKET",
        confirmation="EXECUTE ALPACA PAPER",
        client_order_id=f"baby-quick-close-{symbol.lower()}-{int(episode)}",
    )
    order_id = order.get("id") or order.get("order_id")
    if not order_id:
        raise HTTPException(503, "Broker response missing order id.")
    store.audit("CLOSE", "SUBMITTED", symbol, episode, {"order_id": order_id, "qty": row["quantity"]})
    return {
        "status": "SUBMITTED", "side": "SELL", "symbol": symbol.upper(), "quantity": row["quantity"],
        "environment": "ALPACA_PAPER", "real_money_execution": "DISABLED",
    }


def _ui_file(name):
    path = Path(__file__).with_name(name)
    if not path.exists():
        raise HTTPException(503, f"Missing UI asset: {name}")
    return path.read_text()


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
def quick_page():
    return _ui_file("v1516_quick_ui.html")


@router.get("/enroll", response_class=HTMLResponse)
def enroll_page():
    return _ui_file("v1516_quick_enroll.html")


@router.get("/api/status")
def status(request: Request):
    return {
        "authenticated": session_ok(request.cookies.get("baby_quick_session") or ""),
        "passkeys": store.credential_count(),
        "webauthn_available": WEBAUTHN_AVAILABLE,
        "real_money_execution": "DISABLED",
    }


@router.post("/api/register/begin")
async def register_begin(request: Request):
    if not WEBAUTHN_AVAILABLE:
        raise HTTPException(503, "Python webauthn package is not installed.")
    if store.credential_count() > 0:
        raise HTTPException(409, "A passkey is already enrolled.")
    body = await request.json()
    expected = os.getenv("BABY_QUICK_BOOTSTRAP_TOKEN") or ""
    if not expected or not hmac.compare_digest(str(body.get("bootstrap_code") or ""), expected):
        raise HTTPException(403, "Invalid bootstrap code.")
    options = generate_registration_options(
        rp_id=os.environ["BABY_QUICK_RP_ID"],
        rp_name=os.getenv("BABY_QUICK_RP_NAME", "Baby Quick"),
        user_id=secrets.token_bytes(32),
        user_name="baby-owner",
        user_display_name="Baby Owner",
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.PREFERRED,
            user_verification=UserVerificationRequirement.REQUIRED,
        ),
    )
    challenge_id = store.challenge_put("register", options.challenge, True)
    return {"challenge_id": challenge_id, "options": json.loads(options_to_json(options))}


@router.post("/api/register/complete")
async def register_complete(request: Request):
    body = await request.json()
    challenge = store.challenge_pop(body.get("challenge_id"), "register")
    if not challenge or not challenge.get("bootstrap_ok"):
        raise HTTPException(400, "Registration challenge expired.")
    try:
        verified = verify_registration_response(
            credential=body["credential"],
            expected_challenge=_b64d(challenge["challenge_b64"]),
            expected_origin=os.environ["BABY_QUICK_ORIGIN"],
            expected_rp_id=os.environ["BABY_QUICK_RP_ID"],
            require_user_verification=True,
        )
    except Exception as exc:
        raise HTTPException(400, f"Passkey verification failed: {exc}")
    store.add_credential(verified.credential_id, verified.credential_public_key, verified.sign_count)
    response = Response(content='{"status":"ENROLLED"}', media_type="application/json")
    response.set_cookie(
        "baby_quick_session", make_session(), max_age=43200,
        httponly=True, secure=True, samesite="strict", path="/quick",
    )
    return response


@router.post("/api/login/begin")
def login_begin():
    if not WEBAUTHN_AVAILABLE:
        raise HTTPException(503, "Python webauthn package is not installed.")
    credentials = store.credentials()
    if not credentials:
        raise HTTPException(409, "No passkey enrolled.")
    options = generate_authentication_options(
        rp_id=os.environ["BABY_QUICK_RP_ID"],
        allow_credentials=[PublicKeyCredentialDescriptor(id=_b64d(c["credential_id"])) for c in credentials],
        user_verification=UserVerificationRequirement.REQUIRED,
    )
    challenge_id = store.challenge_put("login", options.challenge)
    return {"challenge_id": challenge_id, "options": json.loads(options_to_json(options))}


@router.post("/api/login/complete")
async def login_complete(request: Request):
    body = await request.json()
    challenge = store.challenge_pop(body.get("challenge_id"), "login")
    if not challenge:
        raise HTTPException(400, "Login challenge expired.")
    credential = body.get("credential") or {}
    credential_id = credential.get("id") or credential.get("rawId")
    row = next((c for c in store.credentials() if c["credential_id"] == credential_id), None)
    if not row:
        raise HTTPException(403, "Unknown passkey.")
    try:
        verified = verify_authentication_response(
            credential=credential,
            expected_challenge=_b64d(challenge["challenge_b64"]),
            expected_origin=os.environ["BABY_QUICK_ORIGIN"],
            expected_rp_id=os.environ["BABY_QUICK_RP_ID"],
            credential_public_key=_b64d(row["public_key_b64"]),
            credential_current_sign_count=int(row["sign_count"]),
            require_user_verification=True,
        )
    except Exception as exc:
        raise HTTPException(403, f"Passkey verification failed: {exc}")
    store.update_sign_count(row["credential_id"], verified.new_sign_count)
    response = Response(content='{"status":"AUTHENTICATED"}', media_type="application/json")
    response.set_cookie(
        "baby_quick_session", make_session(), max_age=43200,
        httponly=True, secure=True, samesite="strict", path="/quick",
    )
    return response


@router.post("/api/logout")
def logout():
    response = Response(content='{"status":"LOGGED_OUT"}', media_type="application/json")
    response.delete_cookie("baby_quick_session", path="/quick")
    return response


@router.get("/api/dashboard")
def api_dashboard(request: Request):
    require_session(request)
    return dashboard()


@router.post("/api/setup/{symbol}/{episode}/approve")
def api_approve(symbol: str, episode: int, request: Request):
    require_session(request)
    return approve_existing(symbol, episode)


@router.post("/api/position/{symbol}/{episode}/close")
def api_close(symbol: str, episode: int, request: Request):
    require_session(request)
    return close_existing(symbol, episode)


@router.post("/api/autopilot/disable")
def api_disable(request: Request):
    require_session(request)
    os.environ["BABY_PAPER_AUTOPILOT_ENABLED"] = "false"
    store.audit("AUTOPILOT_DISABLE", "OK")
    return {"status": "DISABLED", "real_money_execution": "DISABLED"}


@router.get("/s/{token}")
def token_landing(token: str):
    payload = verify_setup_token(token)
    if not payload:
        raise HTTPException(410, "This setup link is expired or invalid.")
    return RedirectResponse(url=f"/quick/?symbol={payload['s']}&episode={payload['e']}", status_code=302)
