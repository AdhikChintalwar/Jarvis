from __future__ import annotations
from datetime import datetime
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
        self.revalidate_limit=max(1,min(int(os.getenv("BABY_REVALIDATE_TOP","5")),20))
        self.scan_timeout_seconds=max(60,int(os.getenv("BABY_SCAN_TIMEOUT_SECONDS","1200")))
        self._stop=threading.Event()
        self._thread=None
        self._work_lock=threading.RLock()
        self.last_runs={}
        self.scan_running=False
        self.revalidation_running=False
        self.current_symbol=None
        self.last_scan_started=None
        self.last_scan_finished=None
        self.last_revalidation_started=None
        self.last_revalidation_finished=None
        self.last_scan_returncode=None
        self.log_path=Path("data/baby_scheduler_events.jsonl")
        self.log_path.parent.mkdir(parents=True,exist_ok=True)

    def start(self):
        if not self.enabled or (self._thread and self._thread.is_alive()):
            return
        self._thread=threading.Thread(target=self._run,name="baby-operating-scheduler",daemon=True)
        self._thread.start()

    def _log(self,event,payload=None):
        item={"at":datetime.now(ET).isoformat(),"event":event,"payload":payload or {}}
        with self.log_path.open("a") as f:
            f.write(json.dumps(item,default=str)+"\n")
        self.last_runs[event]=item["at"]
        return item

    def status(self):
        return {
            "enabled":self.enabled,
            "timezone":"America/New_York",
            "thread_alive":bool(self._thread and self._thread.is_alive()),
            "scan_running":self.scan_running,
            "revalidation_running":self.revalidation_running,
            "current_symbol":self.current_symbol,
            "revalidate_top":self.revalidate_limit,
            "last_scan_started":self.last_scan_started,
            "last_scan_finished":self.last_scan_finished,
            "last_revalidation_started":self.last_revalidation_started,
            "last_revalidation_finished":self.last_revalidation_finished,
            "last_scan_returncode":self.last_scan_returncode,
            "last_runs":self.last_runs,
            "schedule":{
                "pre_market_research":"09:15 ET weekdays",
                "post_open_revalidate":"09:35 ET weekdays",
                "scanner_refresh":"every 15 minutes from 09:45-15:45 ET",
                "afternoon_scan":"15:30 ET (handled once; duplicate 15-minute trigger suppressed)"
            },
            "execution_authority":"NONE"
        }

    def _scan(self):
        if not self._work_lock.acquire(blocking=False):
            self._log("SCAN_SKIPPED",{"reason":"scheduler work already running"})
            return {"status":"SKIPPED","reason":"scheduler work already running"}

        cmd=[sys.executable,"market_scan.py","unusual-volume","--top","50","--deep","0"]
        try:
            self.scan_running=True
            self.last_scan_started=datetime.now(ET).isoformat()
            self._log("SCAN_STARTED",{"command":"market_scan.py unusual-volume --top 50 --deep 0"})

            try:
                r=subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=self.scan_timeout_seconds,
                )
            except subprocess.TimeoutExpired as exc:
                self.last_scan_returncode=None
                self.last_scan_finished=datetime.now(ET).isoformat()
                tail=((exc.stdout or "") if isinstance(exc.stdout,str) else "")[-1000:]
                self._log("SCAN_ERROR",{
                    "kind":"TIMEOUT",
                    "timeout_seconds":self.scan_timeout_seconds,
                    "tail":tail,
                })
                return {"status":"ERROR","reason":"TIMEOUT"}

            self.last_scan_returncode=r.returncode
            self.last_scan_finished=datetime.now(ET).isoformat()
            output=(r.stdout or "") + ("\n"+r.stderr if r.stderr else "")
            self._log("SCAN",{
                "returncode":r.returncode,
                "tail":output[-2000:],
            })

            if r.returncode==0 and self.revalidate:
                return {"status":"READY","returncode":0,"revalidation":self._revalidate()}
            return {"status":"ERROR" if r.returncode else "READY","returncode":r.returncode}

        except Exception as exc:
            self.last_scan_finished=datetime.now(ET).isoformat()
            self._log("SCAN_ERROR",{"kind":type(exc).__name__,"error":str(exc)})
            return {"status":"ERROR","reason":str(exc)}
        finally:
            self.scan_running=False
            self._work_lock.release()

    def _revalidate(self):
        if not self.revalidate:
            self._log("REVALIDATE_SKIPPED",{"reason":"no callback"})
            return {"status":"SKIPPED","reason":"no callback"}

        if not self._work_lock.acquire(blocking=False):
            self._log("REVALIDATE_SKIPPED",{"reason":"scheduler work already running"})
            return {"status":"SKIPPED","reason":"scheduler work already running"}

        self.revalidation_running=True
        self.last_revalidation_started=datetime.now(ET).isoformat()
        self._log("REVALIDATE_STARTED",{"limit":self.revalidate_limit})
        results=[]

        try:
            p=Path("data/scans/unusual-volume_latest.json")
            d=json.loads(p.read_text()) if p.exists() else {}
            rows=d.get("candidates") or d.get("results") or d.get("stocks") or []
            selected=rows[:self.revalidate_limit]

            for index,x in enumerate(selected,1):
                s=x.get("symbol") or x.get("ticker")
                if not s:
                    continue
                s=str(s).upper()
                self.current_symbol=s
                started=datetime.now(ET)
                self._log("REVALIDATE_CANDIDATE_STARTED",{
                    "symbol":s,
                    "index":index,
                    "total":len(selected),
                })
                try:
                    r=self.revalidate(s)
                    item={
                        "symbol":s,
                        "status":r.get("status"),
                        "bridge_failures":r.get("bridge_failures") or [],
                    }
                except Exception as exc:
                    item={"symbol":s,"status":"ERROR","error":str(exc)}
                item["elapsed_seconds"]=round((datetime.now(ET)-started).total_seconds(),3)
                results.append(item)
                self._log("REVALIDATE_CANDIDATE",item)

            self.last_revalidation_finished=datetime.now(ET).isoformat()
            self._log("REVALIDATE",{
                "limit":self.revalidate_limit,
                "candidate_count":len(results),
                "results":results,
            })
            return {"status":"READY","results":results}

        except Exception as exc:
            self.last_revalidation_finished=datetime.now(ET).isoformat()
            self._log("REVALIDATE_ERROR",{"error":str(exc)})
            return {"status":"ERROR","error":str(exc)}
        finally:
            self.current_symbol=None
            self.revalidation_running=False
            self._work_lock.release()

    def _once_per_minute(self,key,fn,now):
        stamp=now.strftime("%Y-%m-%d %H:%M")
        if self.last_runs.get(key)==stamp:
            return
        fn()
        self.last_runs[key]=stamp

    def _run(self):
        seen={}
        while not self._stop.wait(20):
            try:
                now=datetime.now(ET)
                if now.weekday()>=5:
                    continue
                hm=(now.hour,now.minute)
                day=now.strftime("%Y-%m-%d")

                def run_once(name,fn):
                    k=f"{day}:{name}"
                    if seen.get(k):
                        return
                    seen[k]=True
                    fn()

                if hm==(9,15):
                    run_once("0915_SCAN",self._scan)

                if hm==(9,35):
                    run_once("0935_REVALIDATE",self._revalidate)

                if hm==(15,30):
                    run_once("1530_SCAN",self._scan)
                elif (
                    (now.hour>9 or (now.hour==9 and now.minute>=45))
                    and now.hour<16
                    and now.minute%15==0
                ):
                    k=f"{day}:SCAN15:{now.hour}:{now.minute}"
                    if not seen.get(k):
                        seen[k]=True
                        self._scan()

            except Exception as exc:
                self._log("SCHEDULER_LOOP_ERROR",{
                    "kind":type(exc).__name__,
                    "error":str(exc),
                })
