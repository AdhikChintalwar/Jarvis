from __future__ import annotations
import os,requests
from pathlib import Path
from dotenv import load_dotenv

ROOT=Path(__file__).resolve().parents[2];load_dotenv(ROOT/".env",override=False)

class AlfredPointInTimeMacro:
    SERIES={"fed_funds":"DFF","cpi":"CPIAUCSL","unemployment":"UNRATE",
            "treasury_2y":"DGS2","treasury_10y":"DGS10"}
    def __init__(self,key=None,timeout=30):
        self.key=key or os.getenv("FRED_API_KEY");self.timeout=timeout
    def history_as_of(self,series_id,as_of,observation_start="1900-01-01"):
        if not self.key:return []
        d=str(as_of)[:10]
        p={"series_id":series_id,"api_key":self.key,"file_type":"json",
           "realtime_start":d,"realtime_end":d,"observation_start":observation_start}
        r=requests.get("https://api.stlouisfed.org/fred/series/observations",params=p,timeout=self.timeout)
        r.raise_for_status()
        out=[]
        for x in r.json().get("observations",[]):
            try:v=float(x["value"])
            except:continue
            out.append((x["date"],v))
        return out
    def analyze(self,as_of):
        h={k:self.history_as_of(s,as_of) for k,s in self.SERIES.items()}
        def last(k):return h[k][-1][1] if h[k] else None
        ff,cpi,u,y2,y10=map(last,("fed_funds","cpi","unemployment","treasury_2y","treasury_10y"))
        score=50.;known=0;pos=[];risk=[]
        if y2 is not None and y10 is not None:
            known+=1;curve=(y10-y2)*100
            if curve<0:score-=10;risk.append("2s10s yield curve is inverted.")
            else:score+=4;pos.append("2s10s yield curve is positive.")
        else:curve=None
        if u is not None:
            known+=1
            if len(h["unemployment"])>=4:
                ch=u-h["unemployment"][-4][1]
                if ch>=.5:score-=10;risk.append("Unemployment has risen materially over three observations.")
                elif ch<=0:score+=4
        if ff is not None:known+=1
        if cpi is not None and len(h["cpi"])>=13:
            known+=1;yoy=(cpi/h["cpi"][-13][1]-1)*100
            if yoy>=4:score-=8;risk.append("Vintage CPI YoY is elevated.")
            elif yoy<=2.5:score+=5
        else:yoy=None
        return {"regime":"SUPPORTIVE" if score>=58 else "RESTRICTIVE" if score<=42 else "MIXED",
          "score":round(max(0,min(100,score)),2),"confidence":round(known/4*90,2),
          "coverage":round(known/4*100,2),"fed_funds_rate":ff,"cpi_yoy_pct":yoy,
          "unemployment_rate":u,"treasury_2y":y2,"treasury_10y":y10,
          "yield_curve_2s10s_bp":curve,"positives":pos,"risks":risk,
          "unknowns":[] if known==4 else ["missing_vintage_macro_series"],
          "source":"FRED/ALFRED real-time-period API","as_of":str(as_of)[:10],"schema_version":"6.5-PIT"}
