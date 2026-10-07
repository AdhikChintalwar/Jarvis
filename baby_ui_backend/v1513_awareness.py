from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Query


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class BabyAwarenessService:
    """Read-only operational awareness over Baby's persisted SQLite records."""

    def __init__(self, db_path: str | Path | None = None):
        self.db_path = Path(db_path or os.getenv('BABY_UI_DB') or os.getenv('BABY_UI_DB_PATH') or 'data/baby_ui.db')

    def _connect(self):
        db = sqlite3.connect(self.db_path)
        db.row_factory = sqlite3.Row
        return db

    @staticmethod
    def _table_exists(db, table: str) -> bool:
        return bool(db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone())

    @classmethod
    def _columns(cls, db, table: str) -> set[str]:
        if not cls._table_exists(db, table):
            return set()
        return {str(r['name']) for r in db.execute(f'PRAGMA table_info("{table}")')}

    @staticmethod
    def _dicts(rows):
        return [dict(r) for r in rows]

    def _symbol_rows(self, db, table: str, symbol: str, order_candidates, limit=100):
        cols = self._columns(db, table)
        if 'symbol' not in cols:
            return []
        order_col = next((c for c in order_candidates if c in cols), None)
        sql = f'SELECT * FROM "{table}" WHERE UPPER(symbol)=?'
        if order_col:
            sql += f' ORDER BY "{order_col}" DESC'
        sql += ' LIMIT ?'
        return self._dicts(db.execute(sql, (symbol.upper(), int(limit))).fetchall())

    @staticmethod
    def _email_summary(rows):
        success = {'SENT', 'DELIVERED', 'SUCCESS', 'OK'}
        sent = [r for r in rows if r.get('sent_at') or str(r.get('delivery_status') or '').upper() in success]
        failed = [r for r in rows if r.get('error') or str(r.get('delivery_status') or '').upper() in {'FAILED', 'ERROR', 'BOUNCED'}]
        return {
            'delivery_record_count': len(rows),
            'delivery_proven': bool(sent),
            'sent_count': len(sent),
            'failed_count': len(failed),
            'last_delivery': rows[0] if rows else None,
            'proof_rule': 'Email is considered sent only when Baby has a successful email_deliveries record.',
        }

    @staticmethod
    def _forward_summary(rows):
        if not rows:
            return {
                'episodes': 0,
                'latest': None,
                'theoretical': {'t1_hit': False, 't2_hit': False, 'stop_hit': False},
                'paper': {'filled': False, 't1_hit': False, 't2_hit': False, 'stop_hit': False},
            }
        latest = rows[0]
        theoretical = {
            'entry_at': latest.get('theoretical_entry_at'),
            'outcome': latest.get('theoretical_outcome'),
            't1_hit': bool(latest.get('theoretical_t1_hit_at')),
            't1_hit_at': latest.get('theoretical_t1_hit_at'),
            't2_hit': bool(latest.get('theoretical_t2_hit_at')),
            't2_hit_at': latest.get('theoretical_t2_hit_at'),
            'stop_hit': bool(latest.get('theoretical_stop_hit_at')),
            'stop_hit_at': latest.get('theoretical_stop_hit_at'),
            'closed_at': latest.get('theoretical_closed_at'),
        }
        p1 = latest.get('paper_t1_hit_at') or latest.get('t1_hit_at')
        p2 = latest.get('paper_t2_hit_at') or latest.get('t2_hit_at')
        ps = latest.get('paper_stop_hit_at') or latest.get('stop_hit_at')
        paper = {
            'filled': bool(latest.get('filled') or latest.get('fill_price') or latest.get('first_fill_at')),
            'fill_price': latest.get('fill_price'),
            'first_fill_at': latest.get('first_fill_at'),
            'quantity': latest.get('quantity'),
            'alpaca_order_id': latest.get('alpaca_order_id'),
            'order_status': latest.get('order_status'),
            'outcome': latest.get('paper_outcome') or latest.get('outcome'),
            't1_hit': bool(p1), 't1_hit_at': p1,
            't2_hit': bool(p2), 't2_hit_at': p2,
            'stop_hit': bool(ps), 'stop_hit_at': ps,
            'closed_at': latest.get('paper_closed_at') or latest.get('closed_at'),
        }
        return {'episodes': len(rows), 'latest': latest, 'theoretical': theoretical, 'paper': paper}

    @staticmethod
    def _plain_summary(symbol: str, data: dict[str, Any]) -> str:
        parts = [f'Baby activity for {symbol}.']
        cur = (data.get('readiness') or {}).get('current')
        if cur:
            parts.append(f"Current readiness is {cur.get('state') or 'UNKNOWN'}" + (f" ({cur.get('setup_status')})." if cur.get('setup_status') else '.'))
        fwd = data.get('forward_validation') or {}
        paper = fwd.get('paper') or {}
        theoretical = fwd.get('theoretical') or {}
        if paper.get('filled'):
            fill = 'PAPER fill is recorded'
            if paper.get('fill_price') is not None:
                fill += f" at {paper.get('fill_price')}"
            parts.append(fill + '.')
            if paper.get('t1_hit'):
                parts.append(f"PAPER T1 hit is recorded at {paper.get('t1_hit_at')}.")
            elif fwd.get('episodes'):
                parts.append('No PAPER T1 hit is recorded.')
            if paper.get('t2_hit'):
                parts.append(f"PAPER T2 hit is recorded at {paper.get('t2_hit_at')}.")
            if paper.get('stop_hit'):
                parts.append(f"PAPER stop hit is recorded at {paper.get('stop_hit_at')}.")
        elif fwd.get('episodes'):
            parts.append('A forward-validation episode exists, but no PAPER fill is recorded.')
            if theoretical.get('t1_hit'):
                parts.append(f"The theoretical setup reached T1 at {theoretical.get('t1_hit_at')}; this is not an actual PAPER fill result.")
        email = data.get('email') or {}
        if email.get('delivery_proven'):
            last = email.get('last_delivery') or {}
            when = last.get('sent_at') or last.get('created_at')
            subject = last.get('subject')
            msg = 'Email delivery is proven by Baby\'s delivery log'
            if when:
                msg += f' at {when}'
            if subject:
                msg += f' with subject “{subject}”'
            parts.append(msg + '.')
        elif email.get('delivery_record_count'):
            parts.append('Baby has email-delivery records for this symbol, but none prove a successful send.')
        else:
            parts.append('Baby has no email-delivery record proving that an email was sent for this symbol.')
        return ' '.join(parts)

    def symbol_activity(self, symbol: str, limit: int = 100) -> dict[str, Any]:
        symbol = str(symbol or '').strip().upper()
        if not symbol:
            raise ValueError('symbol is required')
        if not self.db_path.exists():
            return {'status': 'DB_NOT_FOUND', 'symbol': symbol, 'db_path': str(self.db_path), 'authority': 'READ_ONLY'}

        with self._connect() as db:
            readiness = self._symbol_rows(db, 'v1511_readiness', symbol, ('updated_at', 'id'), 5)
            history = self._symbol_rows(db, 'v1512_readiness_history', symbol, ('observed_at', 'id'), limit)
            validations = self._symbol_rows(db, 'v1511_forward_validation', symbol, ('t0', 'id'), limit)
            events = self._symbol_rows(db, 'v1511_forward_events', symbol, ('observed_at', 'id'), limit)
            approvals = self._symbol_rows(db, 'v1511_paper_approvals', symbol, ('created_at', 'id'), limit)
            emails = self._symbol_rows(db, 'email_deliveries', symbol, ('created_at', 'sent_at', 'id'), limit)
            alerts = self._symbol_rows(db, 'alerts', symbol, ('created_at', 'id'), limit)
            alert_state = self._symbol_rows(db, 'candidate_alert_state', symbol, ('updated_at',), 5)

        out = {
            'status': 'READY',
            'symbol': symbol,
            'generated_at': _now(),
            'authority': {
                'mode': 'READ_ONLY_OPERATIONAL_EVIDENCE',
                'AI_SCORING_AUTHORITY': '0%',
                'CHAT_EXECUTION_AUTHORITY': 'NONE',
                'REAL_MONEY_EXECUTION': 'DISABLED',
            },
            'readiness': {'current': readiness[0] if readiness else None, 'history': history, 'historical_observation_count': len(history)},
            'forward_validation': self._forward_summary(validations),
            'forward_events': events,
            'paper_approvals': approvals,
            'email': self._email_summary(emails),
            'email_deliveries': emails,
            'alerts': alerts,
            'candidate_alert_state': alert_state[0] if alert_state else None,
        }
        out['summary'] = self._plain_summary(symbol, out)
        return out

    def recent_activity(self, days: int = 7, limit: int = 250) -> dict[str, Any]:
        days = max(1, min(int(days), 3650))
        limit = max(1, min(int(limit), 1000))
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        if not self.db_path.exists():
            return {'status': 'DB_NOT_FOUND', 'days': days, 'activity': {}}
        specs = [
            ('email_deliveries', 'created_at', 'emails'),
            ('v1511_forward_validation', 't0', 'forward_validation'),
            ('v1511_forward_events', 'observed_at', 'forward_events'),
            ('v1512_readiness_history', 'observed_at', 'readiness_history'),
            ('alerts', 'created_at', 'alerts'),
        ]
        result = {key: [] for _, _, key in specs}
        with self._connect() as db:
            for table, time_col, key in specs:
                cols = self._columns(db, table)
                if time_col not in cols:
                    continue
                rows = db.execute(
                    f'SELECT * FROM "{table}" WHERE "{time_col}" >= ? ORDER BY "{time_col}" DESC LIMIT ?',
                    (cutoff, limit),
                ).fetchall()
                result[key] = self._dicts(rows)
        return {'status': 'READY', 'days': days, 'cutoff': cutoff, 'activity': result, 'authority': 'READ_ONLY_OPERATIONAL_EVIDENCE'}


service = BabyAwarenessService()
router = APIRouter(prefix='/api/v1513', tags=['V15.13 Baby Awareness'])


@router.get('/health')
def awareness_health():
    return {'status': 'READY', 'feature': 'BABY_AWARENESS', 'db_exists': service.db_path.exists(), 'db_path': str(service.db_path), 'read_only': True, 'real_money_execution': 'DISABLED'}


@router.get('/awareness/{symbol}')
def awareness_symbol(symbol: str, limit: int = Query(100, ge=1, le=500)):
    return service.symbol_activity(symbol, limit=limit)


@router.get('/awareness/recent/all')
def awareness_recent(days: int = Query(7, ge=1, le=3650), limit: int = Query(250, ge=1, le=1000)):
    return service.recent_activity(days=days, limit=limit)
