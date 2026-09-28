#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import asdict, is_dataclass
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from investor.scanner.quantitative_filter import QuantitativeFilter
from investor.scanner.opportunity_scorer import OpportunityScorer
from investor.scanner.scan_profiles import get_profile
import baby_ui_backend.v1510_opportunity as v1510


DEFAULT_SYMBOLS = ["NCI", "XHLD", "TJGC", "GME", "AAPL", "NVDA", "IWM", "SPY"]


def finite(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except Exception:
        return None


def load_daily(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    cols = {str(c).strip().lower(): c for c in df.columns}

    required = ["open", "high", "low", "close", "volume"]
    missing = [x for x in required if x not in cols]
    if missing:
        raise ValueError(f"{path}: missing columns {missing}; found {list(df.columns)}")

    out = pd.DataFrame({
        "Open": pd.to_numeric(df[cols["open"]], errors="coerce"),
        "High": pd.to_numeric(df[cols["high"]], errors="coerce"),
        "Low": pd.to_numeric(df[cols["low"]], errors="coerce"),
        "Close": pd.to_numeric(df[cols["close"]], errors="coerce"),
        "Volume": pd.to_numeric(df[cols["volume"]], errors="coerce"),
    })

    if "date" in cols:
        out["Date"] = pd.to_datetime(df[cols["date"]], errors="coerce")
    elif "datetime" in cols:
        out["Date"] = pd.to_datetime(df[cols["datetime"]], errors="coerce")
    elif "timestamp" in cols:
        out["Date"] = pd.to_datetime(df[cols["timestamp"]], errors="coerce")
    else:
        out["Date"] = pd.RangeIndex(len(out))

    out = out.dropna(subset=["Open", "High", "Low", "Close", "Volume"]).reset_index(drop=True)
    return out


def obj_dict(x):
    if is_dataclass(x):
        return asdict(x)
    if hasattr(x, "__dict__"):
        return dict(vars(x))
    raise TypeError(type(x))


class ReplayTrajectoryStore:
    """
    Per-symbol, in-memory trajectory store.

    This deliberately prevents historical validation from writing to Baby's
    live SQLite opportunity-trajectory ledger.
    """
    rows_by_symbol: dict[str, list[dict]] = {}

    def __init__(self, *args, **kwargs):
        pass

    @classmethod
    def reset(cls):
        cls.rows_by_symbol = {}

    def record(self, symbol, candidate):
        s = str(symbol).upper()
        row = dict(candidate or {})
        # v1510's trajectory summary consumes scanner observations.
        self.rows_by_symbol.setdefault(s, []).append(row)

    def recent(self, symbol, days=10):
        rows = self.rows_by_symbol.get(str(symbol).upper(), [])
        return rows[-max(int(days), 1):]


def forward_stats(df: pd.DataFrame, idx: int):
    entry = finite(df.iloc[idx]["Close"])
    if not entry or entry <= 0:
        return {}

    out = {}
    for horizon in (5, 10, 20):
        j = idx + horizon
        out[f"return_{horizon}s_pct"] = (
            round((finite(df.iloc[j]["Close"]) / entry - 1) * 100, 2)
            if j < len(df) and finite(df.iloc[j]["Close"]) is not None
            else None
        )

        future = df.iloc[idx + 1:min(len(df), idx + horizon + 1)]
        if len(future):
            max_high = finite(future["High"].max())
            min_low = finite(future["Low"].min())
            out[f"mfe_{horizon}s_pct"] = round((max_high / entry - 1) * 100, 2) if max_high else None
            out[f"mae_{horizon}s_pct"] = round((min_low / entry - 1) * 100, 2) if min_low else None
        else:
            out[f"mfe_{horizon}s_pct"] = None
            out[f"mae_{horizon}s_pct"] = None
    return out


def fmt_date(v):
    if hasattr(v, "strftime"):
        return v.strftime("%Y-%m-%d")
    return str(v)


def run_symbol(symbol: str, path: Path, profile):
    df = load_daily(path)

    qf = QuantitativeFilter()
    scorer = OpportunityScorer()
    stock = SimpleNamespace(
        symbol=symbol,
        provider_symbol=symbol,
        name=symbol,
        exchange="REPLAY",
    )

    timeline = []

    # Scanner requires at least profile.min_history_days. We additionally
    # preserve every production eligibility gate inside QuantitativeFilter.
    for i in range(len(df)):
        hist = df.iloc[:i + 1][["Open", "High", "Low", "Close", "Volume"]].copy()
        date = fmt_date(df.iloc[i]["Date"])
        close = finite(df.iloc[i]["Close"])

        row = {
            "date": date,
            "close": close,
            "scanner_eligible": False,
            "scanner_score_pass": False,
            "stage": "NOT_SCANNED",
            "phase": None,
            "setup_type": None,
            "flow_label": None,
            "flow_score": None,
            "flow_type": None,
            "opportunity_score": None,
            "relative_volume": None,
            "high_volume_days_5d": None,
            "close_location_pct": None,
            "breakout_20d": None,
            "monitoring_signal": None,
            "capital_risk": None,
            "ready": False,
        }

        metrics = qf.analyze(stock=stock, history=hist, profile=profile)
        if metrics is None:
            timeline.append(row)
            continue

        row["scanner_eligible"] = True
        scored = scorer.score(metrics=metrics, profile=profile)
        candidate = obj_dict(scored)

        row.update({
            "opportunity_score": candidate.get("opportunity_score"),
            "flow_score": candidate.get("flow_score"),
            "flow_type": candidate.get("flow_type"),
            "relative_volume": candidate.get("relative_volume"),
            "high_volume_days_5d": candidate.get("high_volume_days_5d"),
            "close_location_pct": candidate.get("close_location_pct"),
            "breakout_20d": candidate.get("breakout_20d"),
        })

        if finite(candidate.get("opportunity_score")) is None or float(candidate["opportunity_score"]) < float(profile.min_score):
            row["stage"] = "SCANNER_SCORE_REJECT"
            timeline.append(row)
            continue

        row["scanner_score_pass"] = True

        # Important architecture match:
        # Live V15.10 receives scanner evidence while V15.5 often lacks bars.
        # We therefore keep report bars absent here, rather than handing V15.5
        # the same historical bars and bypassing the V15.10 bridge.
        intel = v1510.analyze(
            symbol,
            candidate,
            {},
            {
                "status": "RESEARCH",
                "proposal": {
                    "payload": {
                        "setup_status": "RESEARCH",
                        "paper_proposal": {
                            "eligible": False,
                            "status": "WAITING",
                        },
                    }
                },
            },
        )

        row.update({
            "stage": intel.stage,
            "phase": intel.phase,
            "setup_type": intel.setup_type,
            "flow_label": intel.flow.label,
            "monitoring_signal": intel.monitoring_signal,
            "capital_risk": intel.capital_risk.level,
            "ready": bool(intel.ready),
            "evidence_score": intel.evidence_score,
        })
        timeline.append(row)

    monitor_rows = [
        (i, r) for i, r in enumerate(timeline)
        if r.get("stage") in {"MONITOR", "SETUP_FORMING", "SETUP_READY"}
    ]
    first = monitor_rows[0] if monitor_rows else None

    result = {
        "symbol": symbol,
        "sessions": len(df),
        "scanner_eligible_sessions": sum(bool(x.get("scanner_eligible")) for x in timeline),
        "scanner_score_pass_sessions": sum(bool(x.get("scanner_score_pass")) for x in timeline),
        "monitor_sessions": len(monitor_rows),
        "first_monitor": None,
        "timeline": timeline,
    }

    if first:
        idx, r = first
        result["first_monitor"] = dict(r)
        result["first_monitor"].update(forward_stats(df, idx))

    return result


def print_report(results):
    print("\n=== V15.10.3 POINT-IN-TIME OPPORTUNITY-CAPTURE VALIDATION ===")
    print("Production scanner formulas: YES")
    print("Profile: unusual-volume")
    print("Top-50 market-wide ranking reproduced: NO (local symbol set only)")
    print("Point-in-time daily bars: YES")
    print("V15.10 trajectory: sequential, in-memory, no live DB writes")
    print("Threshold tuning from NCI/XHLD outcomes: NONE\n")

    header = (
        f"{'SYM':<6} {'ELIG':>5} {'PASS':>5} {'MON':>5} "
        f"{'FIRST':<11} {'PX':>8} {'PHASE':<18} {'FLOW':<13} "
        f"{'5D':>7} {'10D':>7} {'20D':>7} {'MFE20':>7} {'MAE20':>7}"
    )
    print(header)
    print("-" * len(header))

    for r in results:
        f = r.get("first_monitor") or {}
        def num(k):
            v = f.get(k)
            return "--" if v is None else f"{v:.2f}"
        print(
            f"{r['symbol']:<6} "
            f"{r['scanner_eligible_sessions']:>5} "
            f"{r['scanner_score_pass_sessions']:>5} "
            f"{r['monitor_sessions']:>5} "
            f"{str(f.get('date') or 'NONE'):<11} "
            f"{num('close'):>8} "
            f"{str(f.get('phase') or '--'):<18} "
            f"{str(f.get('flow_label') or '--'):<13} "
            f"{num('return_5s_pct'):>7} "
            f"{num('return_10s_pct'):>7} "
            f"{num('return_20s_pct'):>7} "
            f"{num('mfe_20s_pct'):>7} "
            f"{num('mae_20s_pct'):>7}"
        )

    print("\nInterpretation guardrails:")
    print("- MONITOR means research attention, not a buy signal.")
    print("- Controls are heterogeneous controls, not a statistically matched loser cohort.")
    print("- A small historical set cannot establish predictive validity.")
    print("- Market-wide top-50 ranking is not reproduced by this local replay.")
    print("- Results must not be used to tune thresholds merely to make known winners pass.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", nargs="*", default=DEFAULT_SYMBOLS)
    ap.add_argument("--data-dir", default="data/replay")
    ap.add_argument("--json-out", default="/tmp/baby_v15103_validation.json")
    ap.add_argument("--csv-out", default="/tmp/baby_v15103_validation.csv")
    args = ap.parse_args()

    profile = get_profile("unusual-volume")

    original_store = v1510.OpportunityTrajectoryStore
    v1510.OpportunityTrajectoryStore = ReplayTrajectoryStore
    ReplayTrajectoryStore.reset()

    results = []
    try:
        for symbol in args.symbols:
            symbol = symbol.upper()
            path = Path(args.data_dir) / f"{symbol}.csv"
            if not path.exists():
                print(f"SKIP {symbol}: {path} not found")
                continue
            # Keep each symbol's trajectory isolated.
            ReplayTrajectoryStore.rows_by_symbol.pop(symbol, None)
            results.append(run_symbol(symbol, path, profile))
    finally:
        v1510.OpportunityTrajectoryStore = original_store

    Path(args.json_out).write_text(json.dumps({
        "version": "15.10.3",
        "profile": "unusual-volume",
        "symbols": [r["symbol"] for r in results],
        "limitations": [
            "Daily point-in-time replay; not minute-perfect.",
            "Local symbol set does not reproduce market-wide top-50 ranking.",
            "Controls are heterogeneous and are not a statistically matched loser cohort.",
            "Historical results are process evidence, not a guarantee or return forecast.",
        ],
        "results": results,
    }, indent=2, default=str))

    fields = [
        "symbol", "scanner_eligible_sessions", "scanner_score_pass_sessions", "monitor_sessions",
        "first_monitor_date", "first_monitor_close", "first_monitor_phase", "first_monitor_flow",
        "return_5s_pct", "return_10s_pct", "return_20s_pct", "mfe_20s_pct", "mae_20s_pct",
    ]
    with open(args.csv_out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for r in results:
            f = r.get("first_monitor") or {}
            w.writerow({
                "symbol": r["symbol"],
                "scanner_eligible_sessions": r["scanner_eligible_sessions"],
                "scanner_score_pass_sessions": r["scanner_score_pass_sessions"],
                "monitor_sessions": r["monitor_sessions"],
                "first_monitor_date": f.get("date"),
                "first_monitor_close": f.get("close"),
                "first_monitor_phase": f.get("phase"),
                "first_monitor_flow": f.get("flow_label"),
                "return_5s_pct": f.get("return_5s_pct"),
                "return_10s_pct": f.get("return_10s_pct"),
                "return_20s_pct": f.get("return_20s_pct"),
                "mfe_20s_pct": f.get("mfe_20s_pct"),
                "mae_20s_pct": f.get("mae_20s_pct"),
            })

    print_report(results)
    print(f"\nJSON: {args.json_out}")
    print(f"CSV : {args.csv_out}")


if __name__ == "__main__":
    main()
