from __future__ import annotations

import dataclasses
import enum
import math
import sys
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from investor.analyzer import StockAnalyzer

app = FastAPI(title="BABY Investor UI Bridge", version="1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def serial(value: Any):
    if dataclasses.is_dataclass(value):
        return {k: serial(v) for k, v in dataclasses.asdict(value).items()}
    if isinstance(value, enum.Enum):
        return value.value
    if isinstance(value, dict):
        return {str(k): serial(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [serial(v) for v in value]
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value

def pick(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)

def normalize_report(raw: dict[str, Any]) -> dict[str, Any]:
    report = serial(raw)
    market = serial(report.get("market", {}))
    tech = serial(report.get("technical", {}))
    fund = serial(report.get("fundamentals", {}))
    risk = serial(report.get("risk", {}))
    score = serial(report.get("score", {}))
    health = serial(report.get("financial_health", {}))
    thesis = serial(report.get("thesis", {}))
    pf = serial(report.get("primary_financial") or {})
    verified = pf.get("verified_financials") or {}

    return {
        "ticker": report.get("ticker"),
        "company_name": report.get("company_name"),
        "generated_at": report.get("generated_at"),
        "market": market,
        "technical": tech,
        "fundamentals": fund,
        "risk": risk,
        "score": score,
        "financial_health": health,
        "thesis": thesis,
        "primary_financial": {
            "schema_version": pf.get("schema_version"),
            "primary_source": pf.get("primary_source"),
            "secondary_source": pf.get("secondary_source"),
            "verified_financials": verified,
            "balance_sheet_snapshot": pf.get("balance_sheet_snapshot") or {},
            "cross_validation": pf.get("cross_validation") or {},
        },
        "sec": serial(report.get("sec") or report.get("sec_analysis") or {}),
        "catalysts": serial(report.get("catalysts") or {}),
        "market_context": serial(report.get("market_context") or {}),
        "data_quality": serial(report.get("data_quality") or {}),
        "data_warnings": serial(report.get("data_warnings") or []),
    }

@app.get("/api/health")
def health():
    return {"ok": True, "service": "BABY Investor UI Bridge"}

@app.get("/api/analyze/{ticker}")
def analyze(ticker: str):
    symbol = ticker.strip().upper()
    if not symbol or len(symbol) > 10:
        raise HTTPException(400, "Invalid ticker")
    try:
        raw = StockAnalyzer().analyze(symbol)
        return normalize_report(raw)
    except Exception as exc:
        raise HTTPException(500, f"{type(exc).__name__}: {exc}") from exc
