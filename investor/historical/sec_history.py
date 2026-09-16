import os, re, time
from pathlib import Path
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import requests
from dotenv import load_dotenv

PROJECT_ROOT=Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT/".env",override=False)

class SECHistoricalFilings:
    BASE="https://data.sec.gov"
    ARCH="https://www.sec.gov/Archives/edgar/data"

    def __init__(self,user_agent=None,timeout=30,min_interval=.12,session=None):
        self.ua=user_agent or os.getenv("SEC_USER_AGENT")
        if not self.ua:
            raise RuntimeError("SEC_USER_AGENT required")
        self.timeout=timeout; self.min_interval=min_interval
        self.s=session or requests.Session()
        self.s.headers.update({"User-Agent":self.ua,"Accept-Encoding":"gzip, deflate"})
        self._last=0.0; self._sub_cache={}; self._accept_cache={}

    def _get(self,url):
        wait=self.min_interval-(time.monotonic()-self._last)
        if wait>0: time.sleep(wait)
        r=self.s.get(url,timeout=self.timeout); self._last=time.monotonic()
        r.raise_for_status(); return r

    @staticmethod
    def cik10(cik): return str(int(str(cik))).zfill(10)

    @staticmethod
    def _parse_cutoff(x):
        d=datetime.fromisoformat(str(x).replace("Z","+00:00"))
        if d.tzinfo is None: d=d.replace(tzinfo=timezone.utc)
        return d.astimezone(timezone.utc)

    @staticmethod
    def _acceptance_to_utc(raw):
        if not raw: return None
        s=str(raw).strip()
        # SEC submissions JSON normally supplies YYYY-MM-DDTHH:MM:SS.000Z-like
        # timestamps for recent records. If explicit timezone exists, honor it.
        try:
            d=datetime.fromisoformat(s.replace("Z","+00:00"))
            if d.tzinfo is not None:
                return d.astimezone(timezone.utc).isoformat()
        except ValueError:
            pass
        digits=re.sub(r"\D","",s)
        if len(digits)>=14:
            d=datetime.strptime(digits[:14],"%Y%m%d%H%M%S")
        else:
            try: d=datetime.fromisoformat(s)
            except ValueError: return None
        # Complete-submission ACCEPTANCE-DATETIME is EDGAR Eastern local time.
        return d.replace(tzinfo=ZoneInfo("America/New_York")).astimezone(timezone.utc).isoformat()

    def submissions(self,cik):
        c=self.cik10(cik)
        if c in self._sub_cache: return list(self._sub_cache[c])
        root=self._get(f"{self.BASE}/submissions/CIK{c}.json").json()
        rows=[]
        recent=root.get("filings",{}).get("recent",{})
        if recent:
            keys=list(recent)
            n=len(recent.get("accessionNumber",[]))
            for i in range(n):
                rows.append({k:(recent[k][i] if i<len(recent.get(k,[])) else None) for k in keys})
        for f in root.get("filings",{}).get("files",[]):
            name=f.get("name")
            if not name: continue
            old=self._get(f"{self.BASE}/submissions/{name}").json()
            keys=list(old); n=len(old.get("accessionNumber",[]))
            for i in range(n):
                rows.append({k:(old[k][i] if i<len(old.get(k,[])) else None) for k in keys})
        seen={}
        for x in rows:
            if x.get("accessionNumber"): seen[x["accessionNumber"]]=x
        result=sorted(seen.values(),key=lambda x:(x.get("filingDate") or "",x.get("accessionNumber") or ""))
        self._sub_cache[c]=result
        return list(result)

    def acceptance_datetime(self,cik,accession,row=None):
        key=(self.cik10(cik),accession)
        if key in self._accept_cache:return self._accept_cache[key]
        if row:
            raw=row.get("acceptanceDateTime")
            parsed=self._acceptance_to_utc(raw)
            if parsed:
                self._accept_cache[key]=parsed; return parsed
        c=str(int(str(cik))); a=accession.replace("-","")
        text=self._get(f"{self.ARCH}/{c}/{a}/{accession}.txt").text[:30000]
        m=re.search(r"<ACCEPTANCE-DATETIME>\s*(\d{14})",text,re.I)
        parsed=self._acceptance_to_utc(m.group(1)) if m else None
        self._accept_cache[key]=parsed
        return parsed

    def filings_available(self,cik,as_of,forms=("10-K","10-Q"),include_amendments=False):
        cutoff=self._parse_cutoff(as_of); out=[]
        for f in self.submissions(cik):
            form=f.get("form") or ""; base=form.replace("/A","")
            if base not in forms: continue
            if not include_amendments and form.endswith("/A"): continue
            fd=f.get("filingDate")
            if not fd: continue
            if datetime.fromisoformat(fd).date()>cutoff.date(): continue
            acc=self.acceptance_datetime(cik,f["accessionNumber"],f)
            if not acc: continue  # unknown availability is not allowed to leak into PIT replay
            if self._parse_cutoff(acc)>cutoff: continue
            x=dict(f); x["acceptanceDateTime"]=acc; x["available_at"]=acc
            out.append(x)
        return sorted(out,key=lambda x:x["available_at"])
