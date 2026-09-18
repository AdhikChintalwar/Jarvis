from __future__ import annotations
from datetime import datetime, timezone
from typing import Any

class HistoryService:
    """Research/display chart data only. Never authorizes execution."""
    PERIOD_INTERVALS={
      "1D":("1d","5m"),
      "5D":("5d","15m"),
      "1M":("1mo","1h"),
      "3M":("3mo","1d"),
      "6M":("6mo","1d"),
      "1Y":("1y","1d"),
    }

    def stock(self,symbol:str,range_name:str="1M")->dict[str,Any]:
        symbol=symbol.upper().strip()
        range_name=range_name.upper()
        period,interval=self.PERIOD_INTERVALS.get(range_name,self.PERIOD_INTERVALS["1M"])
        try:
            import yfinance as yf
            df=yf.Ticker(symbol).history(period=period,interval=interval,auto_adjust=False)
            bars=[]
            for idx,row in df.iterrows():
                ts=idx.to_pydatetime().astimezone(timezone.utc).isoformat() if hasattr(idx,"to_pydatetime") else str(idx)
                bars.append({
                  "timestamp":ts,
                  "open":float(row["Open"]) if row.get("Open")==row.get("Open") else None,
                  "high":float(row["High"]) if row.get("High")==row.get("High") else None,
                  "low":float(row["Low"]) if row.get("Low")==row.get("Low") else None,
                  "close":float(row["Close"]) if row.get("Close")==row.get("Close") else None,
                  "volume":float(row["Volume"]) if row.get("Volume")==row.get("Volume") else None,
                })
            return {"status":"READY","symbol":symbol,"range":range_name,
                    "provider":"YFINANCE_RESEARCH_DISPLAY","execution_authority":"NONE","bars":bars}
        except Exception as e:
            return {"status":"NOT_AVAILABLE","symbol":symbol,"range":range_name,
                    "provider":"YFINANCE_RESEARCH_DISPLAY","execution_authority":"NONE",
                    "bars":[],"error":str(e)}
