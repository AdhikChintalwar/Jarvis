from __future__ import annotations
import json, os, threading, traceback
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .adapters import report_from_investment_result
from .notifications import NotificationEngine


def _jsonable(x: Any, depth: int = 0):
    if depth > 8: return str(x)
    if x is None or isinstance(x, (str, int, float, bool)): return x
    if is_dataclass(x): return _jsonable(asdict(x), depth + 1)
    if isinstance(x, dict): return {str(k): _jsonable(v, depth + 1) for k, v in x.items()}
    if isinstance(x, (list, tuple, set)): return [_jsonable(v, depth + 1) for v in x]
    if hasattr(x, '__dict__'):
        return {k: _jsonable(v, depth + 1) for k, v in vars(x).items() if not k.startswith('_') and not callable(v)}
    return str(x)


class ResearchService:
    """Runs the real local StockAnalyzer in a background thread and persists the UI projection.

    This service does not invent a second scoring model. The production analyzer remains the source
    of research facts. If a richer investment-system result is supplied by the project later, the
    same adapter can project it without changing the UI contract.
    """
    def __init__(self, report_dir='data/ui_research', state_dir='data/ui_research/jobs', notifier=None):
        self.report_dir = Path(report_dir); self.report_dir.mkdir(parents=True, exist_ok=True)
        self.state_dir = Path(state_dir); self.state_dir.mkdir(parents=True, exist_ok=True)
        self.notifier = notifier or NotificationEngine()
        self._locks: dict[str, threading.Lock] = {}

    def _state_path(self, symbol): return self.state_dir / f'{symbol.upper()}.json'
    def _report_path(self, symbol): return self.report_dir / f'{symbol.upper()}.json'

    def status(self, symbol: str):
        symbol = symbol.upper()
        p = self._state_path(symbol)
        if p.exists():
            try: return json.loads(p.read_text())
            except Exception: pass
        return {'symbol': symbol, 'status': 'READY' if self._report_path(symbol).exists() else 'NOT_RESEARCHED'}

    def _write_state(self, symbol, **data):
        payload={'symbol':symbol.upper(), **data, 'updated_at':datetime.now(timezone.utc).isoformat()}
        self._state_path(symbol).write_text(json.dumps(payload, indent=2, default=str))
        return payload

    def start(self, symbol: str, force: bool = False):
        symbol=''.join(c for c in symbol.upper().strip() if c.isalnum() or c in '.-')
        if not symbol: raise ValueError('Invalid ticker symbol')
        current=self.status(symbol)
        if current.get('status') == 'RUNNING': return current
        if self._report_path(symbol).exists() and not force:
            return {'symbol':symbol,'status':'READY','message':'Research already exists. Use force=true to refresh.'}
        lock=self._locks.setdefault(symbol, threading.Lock())
        if lock.locked(): return {'symbol':symbol,'status':'RUNNING'}
        self._write_state(symbol,status='QUEUED',stage='Starting Baby research')
        threading.Thread(target=self._run,args=(symbol,lock),daemon=True,name=f'baby-research-{symbol}').start()
        return self.status(symbol)

    def _run(self, symbol, lock):
        with lock:
            started=datetime.now(timezone.utc).isoformat()
            try:
                self._write_state(symbol,status='RUNNING',stage='Loading production StockAnalyzer',started_at=started)
                from investor import StockAnalyzer
                analyzer=StockAnalyzer()
                self._write_state(symbol,status='RUNNING',stage='Running deterministic production research',started_at=started)
                result=analyzer.analyze(symbol)
                self._write_state(symbol,status='RUNNING',stage='Building auditable UI research record',started_at=started)
                ui=report_from_investment_result(symbol,result)
                ui.raw={'production_result':_jsonable(result)}
                target=self._report_path(symbol)
                target.write_text(json.dumps(ui.to_dict(),indent=2,default=str))
                final=self._write_state(symbol,status='READY',stage='Complete',started_at=started,report=str(target),decision=ui.decision,score=ui.score,confidence=ui.confidence,coverage=ui.coverage)
                self.notifier.emit(dedupe_key=f'research-complete:{symbol}:{ui.generated_at[:16]}',title=f'BABY — {symbol} Research Complete',message=f'{ui.decision} · score {ui.score if ui.score is not None else "UNKNOWN"} · coverage {ui.coverage if ui.coverage is not None else "UNKNOWN"}',severity='NOTICE',symbol=symbol,payload=final)
            except Exception as e:
                self._write_state(symbol,status='ERROR',stage='Research failed',started_at=started,error=str(e),traceback=traceback.format_exc())
                self.notifier.emit(dedupe_key=f'research-error:{symbol}',title=f'BABY — {symbol} Research Failed',message=str(e),severity='IMPORTANT',symbol=symbol)
