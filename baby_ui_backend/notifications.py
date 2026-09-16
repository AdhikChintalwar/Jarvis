from __future__ import annotations
import subprocess
from datetime import datetime, timedelta, timezone
from .store import AlertStore

SEVERITIES={'INFO':0,'NOTICE':1,'IMPORTANT':2,'CRITICAL':3}

class NotificationEngine:
    def __init__(self, store=None, cooldown_seconds=300, native=True):
        self.store=store or AlertStore(); self.cooldown_seconds=cooldown_seconds; self.native=native
    def emit(self, *, dedupe_key, title, message, severity='NOTICE', symbol=None, payload=None, force=False):
        severity=severity.upper()
        cutoff=(datetime.now(timezone.utc)-timedelta(seconds=self.cooldown_seconds)).isoformat()
        if not force and self.store.recent_duplicate(dedupe_key,cutoff): return {'sent':False,'reason':'COOLDOWN'}
        alert={'dedupe_key':dedupe_key,'title':title,'message':message,'severity':severity,'symbol':symbol,'payload':payload or {}}
        alert['id']=self.store.add(alert)
        if self.native and SEVERITIES.get(severity,1)>=1: self._macos(title,message)
        return {'sent':True,'alert':alert}
    @staticmethod
    def _macos(title,message):
        # No shell=True; escape handled by argv to osascript.
        script='display notification ' + repr(str(message)) + ' with title ' + repr(str(title))
        try: subprocess.run(['osascript','-e',script],check=False,capture_output=True,text=True,timeout=3)
        except Exception: pass
