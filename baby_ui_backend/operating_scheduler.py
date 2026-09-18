from __future__ import annotations
from datetime import datetime, time as dtime
from zoneinfo import ZoneInfo
from pathlib import Path
import json
import os
import subprocess
import sys
import threading

ET=ZoneInfo("America/New_York")

class BabyOperatingScheduler:
    """Research-only operating scheduler. It never submits broker orders."""
    def __init__(self, revalidate=None):
        self.revalidate=revalidate
        self.enabled=os.getenv("BABY_RESEARCH_SCHEDULER","ENABLED").upper()=="ENABLED"
        self._stop=threading.Event()
        self._thread=None
        self.last_runs={}
        self.log_path=Path("data/baby_scheduler_events.jsonl")
        self.log_path.parent.mkdir(parents=True,exist_ok=True)

    def start(self):
        if not self.enabled or (self._thread and self._thread.is_alive()):
            return
        self._thread=threading.Thread(target=self._run,name="baby-operating-scheduler",daemon=True)
        self._thread.start()

    def _log(self,event,payload=None):
        item={"at":datetime.now(ET).isoformat(),"event":event,"payload":payload or {}}
        with self.log_path.open("a") as f:f.write(json.dumps(item)+"\n")
        self.last_runs[event]=item["at"]

    def status(self):
        return {"enabled":self.enabled,"timezone":"America/New_York",
                "last_runs":self.last_runs,
                "schedule":{
                  "pre_market_research":"09:15 ET weekdays",
                  "post_open_revalidate":"09:35 ET weekdays",
                  "scanner_refresh":"every 15 minutes from 09:45-15:45 ET",
                  "afternoon_scan":"15:30 ET weekdays"
                },
                "execution_authority":"NONE"}

    def _scan(self):
        cmd=[sys.executable,"market_scan.py","unusual-volume","--top","50","--deep","0"]
        r=subprocess.run(cmd,capture_output=True,text=True,timeout=1200)
        self._log("SCAN",{"returncode":r.returncode,"tail":(r.stdout or r.stderr)[-2000:]})

    def _revalidate(self):
        if not self.revalidate:
            self._log("REVALIDATE_SKIPPED",{"reason":"no callback"})
            return
        try:
            p=Path("data/scans/unusual-volume_latest.json")
            d=json.loads(p.read_text()) if p.exists() else {}
            rows=d.get("candidates") or d.get("results") or d.get("stocks") or []
            results=[]
            for x in rows[:20]:
                s=x.get("symbol") or x.get("ticker")
                if not s:continue
                try:
                    r=self.revalidate(s)
                    results.append({"symbol":s,"status":r.get("status"),
                                    "bridge_failures":r.get("bridge_failures") or []})
                except Exception as e:
                    results.append({"symbol":s,"status":"ERROR","error":str(e)})
            self._log("REVALIDATE",{"results":results})
        except Exception as e:
            self._log("REVALIDATE_ERROR",{"error":str(e)})

    def _once_per_minute(self,key,fn,now):
        stamp=now.strftime("%Y-%m-%d %H:%M")
        if self.last_runs.get(key)==stamp:return
        fn()
        self.last_runs[key]=stamp

    def _run(self):
        seen={}
        while not self._stop.wait(20):
            now=datetime.now(ET)
            if now.weekday()>=5:continue
            hm=(now.hour,now.minute)
            day=now.strftime("%Y-%m-%d")
            def run_once(name,fn):
                k=f"{day}:{name}"
                if seen.get(k):return
                seen[k]=True
                fn()
            if hm==(9,15):run_once("0915_SCAN",self._scan)
            if hm==(9,35):run_once("0935_REVALIDATE",self._revalidate)
            if now.hour==15 and now.minute==30:run_once("1530_SCAN",self._scan)
            if (now.hour>9 or (now.hour==9 and now.minute>=45)) and now.hour<16 and now.minute%15==0:
                k=f"{day}:SCAN15:{now.hour}:{now.minute}"
                if not seen.get(k):
                    seen[k]=True
                    self._scan()
