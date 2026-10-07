from __future__ import annotations

import io
import json
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Query
from fastapi.responses import Response

ET = ZoneInfo("America/New_York")
router = APIRouter(prefix="/api/v1512/reports", tags=["Baby V15.12 Reports"])


def _dt(v):
    if not v:
        return None
    try:
        d = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d
    except Exception:
        return None


def _et_date(v):
    d = _dt(v)
    return d.astimezone(ET).date().isoformat() if d else None


def _fmt_et(v):
    d = _dt(v)
    return d.astimezone(ET).strftime("%b %d, %Y %I:%M %p ET") if d else None


def _f(v):
    try:
        return float(v)
    except Exception:
        return None


def _days_between(start, end=None):
    s = _dt(start)
    if not s:
        return None
    e = _dt(end) or datetime.now(timezone.utc)
    return round(max(0.0, (e - s).total_seconds() / 86400.0), 2)


def theoretical_status(outcome):
    o = str(outcome or "UNFILLED").upper()
    return {
        "UNFILLED": "WAITING_FOR_ENTRY",
        "OPEN": "IN_PROGRESS",
        "T1_HIT": "PARTIAL_SUCCESS",
        "T2_HIT": "SUCCESS",
        "STOPPED": "FAILED",
        "T1_THEN_STOP": "T1_THEN_STOP",
        "EXPIRED": "EXPIRED",
        "CANCELLED": "CANCELLED",
    }.get(o, o or "UNRESOLVED")


def paper_status(outcome, traded=False):
    o = str(outcome or "").upper()
    if not traded and o in {"", "NOT_EXECUTED"}:
        return "NOT_TRADED"
    return {
        "NOT_EXECUTED": "NOT_TRADED",
        "UNFILLED": "ORDER_UNFILLED",
        "OPEN": "IN_PROGRESS",
        "T1_HIT": "PARTIAL_SUCCESS",
        "T2_HIT": "SUCCESS",
        "STOPPED": "FAILED",
        "T1_THEN_STOP": "T1_THEN_STOP",
        "EXPIRED": "EXPIRED",
        "CANCELLED": "CANCELLED",
    }.get(o, o or "UNRESOLVED")


class ReportService:
    def __init__(self, path="data/baby_ui.db"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _db(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        return db

    def _init(self):
        with self._db() as db:
            db.executescript(
                '''
                CREATE TABLE IF NOT EXISTS v1512_readiness_history(
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  symbol TEXT NOT NULL,
                  state TEXT NOT NULL,
                  readiness_potential INTEGER,
                  reason TEXT,
                  setup_status TEXT,
                  failures_json TEXT,
                  observed_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_v1512_hist_time
                  ON v1512_readiness_history(observed_at);
                CREATE INDEX IF NOT EXISTS idx_v1512_hist_symbol
                  ON v1512_readiness_history(symbol,observed_at);
                '''
            )
            db.commit()

    @staticmethod
    def _cutoff(days):
        days = max(1, min(int(days or 30), 3650))
        now = datetime.now(timezone.utc)
        return now.timestamp() - days * 86400, days

    def _all(self, table):
        with self._db() as db:
            try:
                return [dict(r) for r in db.execute(f"SELECT * FROM {table}").fetchall()]
            except sqlite3.OperationalError:
                return []

    def _filter_time(self, rows, field, cutoff_ts):
        out = []
        for r in rows:
            d = _dt(r.get(field))
            if d and d.timestamp() >= cutoff_ts:
                out.append(r)
        return out

    def baby_performance(self, days=30):
        cutoff_ts, _ = self._cutoff(days)
        rows = self._filter_time(self._all("v1511_forward_validation"), "t0", cutoff_ts)
        rows.sort(key=lambda r: r.get("t0") or "", reverse=True)
        out = []
        for r in rows:
            t_out = r.get("theoretical_outcome") or r.get("outcome") or "UNFILLED"
            p_out = r.get("paper_outcome") or ("OPEN" if r.get("filled") else "NOT_EXECUTED")
            traded = bool(r.get("alpaca_order_id") or r.get("quantity") or r.get("filled"))
            close_at = r.get("theoretical_closed_at") or r.get("closed_at")
            out.append({
                "symbol": r.get("symbol"),
                "ready_episode": r.get("ready_episode"),
                "setup_type": r.get("setup_type") or "UNKNOWN",
                "ready_at": _fmt_et(r.get("t0")),
                "ready_at_raw": r.get("t0"),
                "entry": _f(r.get("entry")),
                "entry_hit_at": _fmt_et(r.get("theoretical_entry_at")),
                "entry_hit_at_raw": r.get("theoretical_entry_at"),
                "target1": _f(r.get("target1")),
                "t1_hit_at": _fmt_et(r.get("theoretical_t1_hit_at") or r.get("t1_hit_at")),
                "t1_hit_at_raw": r.get("theoretical_t1_hit_at") or r.get("t1_hit_at"),
                "target2": _f(r.get("target2")),
                "t2_hit_at": _fmt_et(r.get("theoretical_t2_hit_at") or r.get("t2_hit_at")),
                "t2_hit_at_raw": r.get("theoretical_t2_hit_at") or r.get("t2_hit_at"),
                "invalidation": _f(r.get("invalidation")),
                "invalidation_hit_at": _fmt_et(r.get("theoretical_stop_hit_at") or r.get("stop_hit_at")),
                "invalidation_hit_at_raw": r.get("theoretical_stop_hit_at") or r.get("stop_hit_at"),
                "status": theoretical_status(t_out),
                "outcome": str(t_out).upper(),
                "mfe_pct": _f(r.get("theoretical_mfe_pct") if r.get("theoretical_mfe_pct") is not None else r.get("mfe_pct")),
                "mae_pct": _f(r.get("theoretical_mae_pct") if r.get("theoretical_mae_pct") is not None else r.get("mae_pct")),
                "days_open": _days_between(r.get("theoretical_entry_at") or r.get("t0"), close_at),
                "paper_traded": traded,
                "paper_status": paper_status(p_out, traded),
                "paper_order_id": r.get("alpaca_order_id"),
                "paper_quantity": _f(r.get("quantity")),
                "paper_fill_at": _fmt_et(r.get("first_fill_at")),
                "paper_fill_price": _f(r.get("fill_price")),
                "paper_t1_hit_at": _fmt_et(r.get("paper_t1_hit_at")),
                "paper_t2_hit_at": _fmt_et(r.get("paper_t2_hit_at")),
                "paper_invalidation_hit_at": _fmt_et(r.get("paper_stop_hit_at")),
                "paper_mfe_pct": _f(r.get("paper_mfe_pct")),
                "paper_mae_pct": _f(r.get("paper_mae_pct")),
            })
        return out

    def daily(self, days=30):
        cutoff_ts, _ = self._cutoff(days)
        hist = self._filter_time(self._all("v1512_readiness_history"), "observed_at", cutoff_ts)
        led = self._filter_time(self._all("v1511_forward_validation"), "t0", cutoff_ts)
        approvals = self._filter_time(self._all("v1511_paper_approvals"), "created_at", cutoff_ts)
        emails = self._filter_time(self._all("email_deliveries"), "created_at", cutoff_ts)

        by_day = defaultdict(lambda: {
            "symbols": set(),
            "reached": defaultdict(set),
            "last": {},
            "blockers": Counter(),
            "setup_ready_episodes": 0,
            "approvals_created": 0,
            "paper_orders_submitted": 0,
            "paper_fills": 0,
            "emails_sent": 0,
            "email_failures": 0,
        })

        for r in hist:
            day = _et_date(r.get("observed_at"))
            if not day:
                continue
            sym = str(r.get("symbol") or "").upper()
            st = str(r.get("state") or "UNKNOWN").upper()
            if sym:
                by_day[day]["symbols"].add(sym)
                by_day[day]["reached"][st].add(sym)
                prev = by_day[day]["last"].get(sym)
                if not prev or str(r.get("observed_at")) > str(prev.get("observed_at")):
                    by_day[day]["last"][sym] = r
            try:
                failures = json.loads(r.get("failures_json") or "[]")
            except Exception:
                failures = []
            for f in set(str(x) for x in failures if x):
                by_day[day]["blockers"][f] += 1

        for r in led:
            day = _et_date(r.get("t0"))
            if not day:
                continue
            by_day[day]["setup_ready_episodes"] += 1
            if r.get("alpaca_order_id"):
                by_day[day]["paper_orders_submitted"] += 1
            if r.get("filled"):
                by_day[day]["paper_fills"] += 1

        for r in approvals:
            day = _et_date(r.get("created_at"))
            if day:
                by_day[day]["approvals_created"] += 1

        for r in emails:
            day = _et_date(r.get("created_at"))
            if not day:
                continue
            status = str(r.get("delivery_status") or "").upper()
            if status == "SENT":
                by_day[day]["emails_sent"] += 1
            elif status == "FAILED":
                by_day[day]["email_failures"] += 1

        out = []
        for day in sorted(by_day.keys(), reverse=True):
            x = by_day[day]
            closing = Counter(str(v.get("state") or "UNKNOWN").upper() for v in x["last"].values())
            reached = {k: len(v) for k, v in x["reached"].items()}
            out.append({
                "date": day,
                "symbols_observed": len(x["symbols"]),
                "closing_states": dict(closing),
                "reached_states": reached,
                "monitor": reached.get("MONITOR", 0),
                "setup_forming": reached.get("SETUP_FORMING", 0),
                "active_setup": reached.get("ACTIVE_SETUP", 0),
                "near_ready": reached.get("NEAR_READY", 0),
                "setup_ready": reached.get("SETUP_READY", 0),
                "setup_ready_episodes": x["setup_ready_episodes"],
                "approvals_created": x["approvals_created"],
                "paper_orders_submitted": x["paper_orders_submitted"],
                "paper_fills": x["paper_fills"],
                "emails_sent": x["emails_sent"],
                "email_failures": x["email_failures"],
                "top_blockers": [{"blocker": k, "count": v} for k, v in x["blockers"].most_common(8)],
            })
        return out

    def blockers(self, days=30):
        cutoff_ts, _ = self._cutoff(days)
        hist = self._filter_time(self._all("v1512_readiness_history"), "observed_at", cutoff_ts)
        uniq = set()
        counts = Counter()
        symbols = defaultdict(set)
        for r in hist:
            day = _et_date(r.get("observed_at"))
            sym = str(r.get("symbol") or "").upper()
            try:
                failures = json.loads(r.get("failures_json") or "[]")
            except Exception:
                failures = []
            for f in set(str(x) for x in failures if x):
                key = (day, sym, f)
                if key in uniq:
                    continue
                uniq.add(key)
                counts[f] += 1
                symbols[f].add(sym)
        return [{"blocker": k, "count": v, "symbols": sorted(symbols[k])[:20]} for k, v in counts.most_common()]

    def setup_types(self, days=30):
        rows = self.baby_performance(days)
        groups = defaultdict(list)
        for r in rows:
            groups[r.get("setup_type") or "UNKNOWN"].append(r)
        out = []
        for name, g in groups.items():
            entered = [r for r in g if r["entry_hit_at_raw"]]
            t1 = [r for r in entered if r["outcome"] in {"T1_HIT","T2_HIT","T1_THEN_STOP"}]
            t2 = [r for r in entered if r["outcome"] == "T2_HIT"]
            failed = [r for r in entered if r["outcome"] == "STOPPED"]
            open_ = [r for r in entered if r["outcome"] in {"OPEN","T1_HIT"}]
            out.append({
                "setup_type": name,
                "ready_episodes": len(g),
                "entered": len(entered),
                "t1_hits": len(t1),
                "t2_hits": len(t2),
                "failed_before_t1": len(failed),
                "open": len(open_),
                "entry_rate_pct": round(100*len(entered)/len(g),1) if g else None,
                "t1_rate_pct": round(100*len(t1)/len(entered),1) if entered else None,
                "t2_rate_pct": round(100*len(t2)/len(entered),1) if entered else None,
                "stop_before_t1_rate_pct": round(100*len(failed)/len(entered),1) if entered else None,
            })
        return sorted(out, key=lambda x: x["ready_episodes"], reverse=True)

    def alert_health(self, days=30):
        cutoff_ts, _ = self._cutoff(days)
        emails = self._filter_time(self._all("email_deliveries"), "created_at", cutoff_ts)
        status = Counter(str(r.get("delivery_status") or "UNKNOWN").upper() for r in emails)
        events = Counter(str(r.get("event_type") or "UNKNOWN").upper() for r in emails)
        approvals = self._filter_time(self._all("v1511_paper_approvals"), "created_at", cutoff_ts)
        approval_states = Counter(str(r.get("status") or "UNKNOWN").upper() for r in approvals)
        return {
            "email_total": len(emails),
            "email_status": dict(status),
            "email_events": dict(events),
            "approval_total": len(approvals),
            "approval_status": dict(approval_states),
        }

    def overview(self, days=30):
        cutoff_ts, _ = self._cutoff(days)

        history = self._filter_time(
            self._all("v1512_readiness_history"),
            "observed_at",
            cutoff_ts,
        )

        history_symbols = sorted({
            str(r.get("symbol") or "").upper()
            for r in history
            if r.get("symbol")
        })

        history_times = [
            r.get("observed_at")
            for r in history
            if r.get("observed_at")
        ]

        historical_backfill = [
            r for r in history
            if r.get("source")
        ]

        perf = self.baby_performance(days)
        entered = [r for r in perf if r["entry_hit_at_raw"]]
        t1 = [r for r in entered if r["outcome"] in {"T1_HIT","T2_HIT","T1_THEN_STOP"}]
        t2 = [r for r in entered if r["outcome"] == "T2_HIT"]
        failed = [r for r in entered if r["outcome"] == "STOPPED"]
        open_ = [r for r in perf if r["status"] in {"IN_PROGRESS","PARTIAL_SUCCESS","WAITING_FOR_ENTRY"}]
        traded = [r for r in perf if r["paper_traded"]]
        return {
            "generated_at": _fmt_et(datetime.now(timezone.utc).isoformat()),
            "days": max(1, min(int(days or 30), 3650)),
            "summary": {
                "historical_observations": len(history),
                "historical_backfill_observations": len(historical_backfill),
                "symbols_monitored": len(history_symbols),
                "history_first_seen": _fmt_et(min(history_times)) if history_times else None,
                "history_last_seen": _fmt_et(max(history_times)) if history_times else None,
                "setup_ready_episodes": len(perf),
                "unique_symbols": len(set(r["symbol"] for r in perf if r["symbol"])),
                "entries_established": len(entered),
                "waiting_for_entry": sum(1 for r in perf if r["status"] == "WAITING_FOR_ENTRY"),
                "open_setups": len(open_),
                "t1_hits": len(t1),
                "t2_hits": len(t2),
                "failed_before_t1": len(failed),
                "actual_paper_trades": len(traded),
                "entry_rate_pct": round(100*len(entered)/len(perf),1) if perf else None,
                "t1_rate_pct": round(100*len(t1)/len(entered),1) if entered else None,
                "t2_rate_pct": round(100*len(t2)/len(entered),1) if entered else None,
                "stop_before_t1_rate_pct": round(100*len(failed)/len(entered),1) if entered else None,
            },
            "daily": self.daily(days),
            "baby_performance": perf,
            "paper_trades": [r for r in perf if r["paper_traded"]],
            "open_setups": open_,
            "blockers": self.blockers(days),
            "setup_types": self.setup_types(days),
            "alert_health": self.alert_health(days),
            "definitions": {
                "WAITING_FOR_ENTRY": "SETUP_READY was issued but the frozen entry has not yet been established.",
                "IN_PROGRESS": "Entry was established and neither final success nor failure has occurred.",
                "PARTIAL_SUCCESS": "T1 was reached after entry; T2 remains unresolved.",
                "SUCCESS": "T2 was reached after entry.",
                "FAILED": "Invalidation was reached after entry before T1.",
                "T1_THEN_STOP": "T1 was reached, then invalidation was reached before T2.",
                "NOT_TRADED": "Baby generated the setup, but no Alpaca PAPER order was submitted for it.",
            },
            "real_money_execution": "DISABLED",
            "quantity_source": "USER_SELECTED",
        }


service = ReportService()


def _money(v):
    try:
        return f"${float(v):,.2f}"
    except Exception:
        return "--"


def _pct(v):
    try:
        return f"{float(v):.2f}%"
    except Exception:
        return "--"


def _report_lines(data):
    s = data["summary"]
    lines = [
        "BABY V15.12 - REPORTS & PERFORMANCE ANALYTICS",
        f"Generated: {data['generated_at']}",
        f"Window: last {data['days']} day(s)",
        "",
        "SUMMARY",
        f"Historical observations: {s.get('historical_observations', 0)}",
        f"Backfilled historical observations: {s.get('historical_backfill_observations', 0)}",
        f"Symbols monitored: {s.get('symbols_monitored', 0)}",
        f"History range: {s.get('history_first_seen') or '--'} to {s.get('history_last_seen') or '--'}",
        "",
        "SETUP_READY PERFORMANCE",
        f"SETUP_READY episodes: {s['setup_ready_episodes']}",
        f"Unique SETUP_READY symbols: {s['unique_symbols']}",
        f"Entries established: {s['entries_established']}",
        f"T1 hits: {s['t1_hits']} | T2 hits: {s['t2_hits']} | Failed before T1: {s['failed_before_t1']}",
        f"Entry rate: {_pct(s['entry_rate_pct'])} | T1 rate after entry: {_pct(s['t1_rate_pct'])} | T2 rate after entry: {_pct(s['t2_rate_pct'])}",
        f"Actual Alpaca PAPER trades: {s['actual_paper_trades']}",
        "",
        "BABY SETUP PERFORMANCE",
        "Symbol | Ready | Entry | Entry hit | T1 | T1 hit | T2 | T2 hit | Stop | Stop hit | Status | PAPER",
    ]
    for r in data["baby_performance"]:
        lines.append(" | ".join([
            str(r["symbol"] or ""),
            str(r["ready_at"] or "--"),
            _money(r["entry"]),
            str(r["entry_hit_at"] or "--"),
            _money(r["target1"]),
            str(r["t1_hit_at"] or "--"),
            _money(r["target2"]),
            str(r["t2_hit_at"] or "--"),
            _money(r["invalidation"]),
            str(r["invalidation_hit_at"] or "--"),
            str(r["status"]),
            str(r["paper_status"]),
        ]))
    lines += ["", "DAILY ACTIVITY"]
    for r in data["daily"]:
        lines.append(
            f"{r['date']}: observed {r['symbols_observed']} | monitor {r['monitor']} | forming {r['setup_forming']} | "
            f"active {r['active_setup']} | near-ready {r['near_ready']} | ready episodes {r['setup_ready_episodes']} | "
            f"PAPER orders {r['paper_orders_submitted']} | fills {r['paper_fills']}"
        )
    lines += ["", "TOP BLOCKERS"]
    for r in data["blockers"][:25]:
        lines.append(f"{r['blocker']}: {r['count']} symbol-day occurrence(s)")
    lines += [
        "",
        "NOTES",
        "- Baby performance is measured from the frozen SETUP_READY plan even if the user did not trade it.",
        "- Actual Alpaca PAPER performance begins only after an actual broker fill.",
        "- Price action before theoretical entry or PAPER fill is not counted.",
        "- Open/unresolved setups are not counted as wins or losses.",
        "- Real-money execution remains DISABLED. Quantity remains USER_SELECTED.",
    ]
    return lines


def _simple_pdf(lines):
    def esc(s):
        return str(s).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    wrapped = []
    for line in lines:
        text = str(line)
        if not text:
            wrapped.append("")
            continue
        while len(text) > 105:
            cut = text.rfind(" ", 0, 105)
            if cut < 50:
                cut = 105
            wrapped.append(text[:cut])
            text = text[cut:].lstrip()
        wrapped.append(text)

    pages = [wrapped[i:i+52] for i in range(0, len(wrapped), 52)] or [[]]
    objects = []
    catalog_id, pages_id, font_id = 1, 2, 3
    next_id = 4
    page_ids, content_ids = [], []
    for _ in pages:
        page_ids.append(next_id); next_id += 1
        content_ids.append(next_id); next_id += 1

    objects.append((catalog_id, f"<< /Type /Catalog /Pages {pages_id} 0 R >>"))
    kids = " ".join(f"{pid} 0 R" for pid in page_ids)
    objects.append((pages_id, f"<< /Type /Pages /Count {len(page_ids)} /Kids [{kids}] >>"))
    objects.append((font_id, "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"))

    for page_no, page in enumerate(pages):
        pid, cid = page_ids[page_no], content_ids[page_no]
        stream = ["BT", "/F1 8 Tf", "44 760 Td", "10 TL"]
        for line in page:
            stream.append(f"({esc(line)}) Tj")
            stream.append("T*")
        stream.append("ET")
        data = "\n".join(stream).encode("latin-1", "replace")
        objects.append((pid, f"<< /Type /Page /Parent {pages_id} 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 {font_id} 0 R >> >> /Contents {cid} 0 R >>"))
        objects.append((cid, b"<< /Length %d >>\nstream\n" % len(data) + data + b"\nendstream"))

    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = {0: 0}
    for oid, body in sorted(objects, key=lambda x: x[0]):
        offsets[oid] = out.tell()
        out.write(f"{oid} 0 obj\n".encode())
        out.write(body if isinstance(body, bytes) else body.encode("latin-1", "replace"))
        out.write(b"\nendobj\n")
    xref = out.tell()
    max_id = max(offsets)
    out.write(f"xref\n0 {max_id+1}\n".encode())
    out.write(b"0000000000 65535 f \n")
    for i in range(1, max_id+1):
        out.write(f"{offsets.get(i,0):010d} 00000 n \n".encode())
    out.write(f"trailer\n<< /Size {max_id+1} /Root {catalog_id} 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return out.getvalue()


def build_pdf(data):
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import landscape, letter
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import inch
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak

        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=landscape(letter), rightMargin=24, leftMargin=24, topMargin=24, bottomMargin=24)
        styles = getSampleStyleSheet()
        story = [
            Paragraph("Baby V15.12 - Reports & Performance Analytics", styles["Title"]),
            Paragraph(f"Generated {data['generated_at']} - Window: {data['days']} day(s)", styles["Normal"]),
            Spacer(1, 10),
        ]
        s = data["summary"]
        summary = [
            ["Metric","Value"],
            ["SETUP_READY episodes", s["setup_ready_episodes"]],
            ["Entries established", s["entries_established"]],
            ["T1 hit rate after entry", _pct(s["t1_rate_pct"])],
            ["T2 hit rate after entry", _pct(s["t2_rate_pct"])],
            ["Stop-before-T1 rate", _pct(s["stop_before_t1_rate_pct"])],
            ["Actual Alpaca PAPER trades", s["actual_paper_trades"]],
        ]
        t = Table(summary, colWidths=[2.7*inch, 1.6*inch])
        t.setStyle(TableStyle([
            ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#0b1b28")),
            ("TEXTCOLOR",(0,0),(-1,0),colors.white),
            ("GRID",(0,0),(-1,-1),0.25,colors.grey),
            ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
            ("FONTSIZE",(0,0),(-1,-1),8),
            ("VALIGN",(0,0),(-1,-1),"TOP"),
        ]))
        story += [t, Spacer(1, 14), Paragraph("Baby Setup Performance", styles["Heading2"])]
        headers = ["Symbol","Ready","Entry","Entry hit","T1","T1 hit","T2","T2 hit","Stop","Stop hit","Status","PAPER"]
        rows = [headers]
        for r in data["baby_performance"]:
            rows.append([
                r["symbol"], r["ready_at"] or "--", _money(r["entry"]), r["entry_hit_at"] or "--",
                _money(r["target1"]), r["t1_hit_at"] or "--", _money(r["target2"]), r["t2_hit_at"] or "--",
                _money(r["invalidation"]), r["invalidation_hit_at"] or "--", r["status"], r["paper_status"]
            ])
        tab = Table(rows, repeatRows=1, colWidths=[.45*inch,.9*inch,.55*inch,.9*inch,.55*inch,.9*inch,.55*inch,.9*inch,.55*inch,.9*inch,.85*inch,.8*inch])
        tab.setStyle(TableStyle([
            ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#0b1b28")),
            ("TEXTCOLOR",(0,0),(-1,0),colors.white),
            ("GRID",(0,0),(-1,-1),0.2,colors.HexColor("#9aa7b3")),
            ("FONTSIZE",(0,0),(-1,-1),6),
            ("VALIGN",(0,0),(-1,-1),"TOP"),
        ]))
        story.append(tab)
        story += [PageBreak(), Paragraph("Daily Activity", styles["Heading2"])]
        daily_rows = [["Date","Observed","Monitor","Forming","Active","Near Ready","Ready Episodes","PAPER Orders","Fills"]]
        for r in data["daily"]:
            daily_rows.append([r["date"],r["symbols_observed"],r["monitor"],r["setup_forming"],r["active_setup"],r["near_ready"],r["setup_ready_episodes"],r["paper_orders_submitted"],r["paper_fills"]])
        dt = Table(daily_rows, repeatRows=1)
        dt.setStyle(TableStyle([("GRID",(0,0),(-1,-1),.25,colors.grey),("FONTSIZE",(0,0),(-1,-1),7),("BACKGROUND",(0,0),(-1,0),colors.HexColor("#0b1b28")),("TEXTCOLOR",(0,0),(-1,0),colors.white)]))
        story.append(dt)
        story += [Spacer(1, 14), Paragraph("Top Blockers", styles["Heading2"])]
        br = [["Blocker","Count","Symbols"]] + [[r["blocker"],r["count"],", ".join(r["symbols"][:12])] for r in data["blockers"][:30]]
        bt = Table(br, repeatRows=1, colWidths=[3.6*inch,.7*inch,6*inch])
        bt.setStyle(TableStyle([("GRID",(0,0),(-1,-1),.25,colors.grey),("FONTSIZE",(0,0),(-1,-1),7),("BACKGROUND",(0,0),(-1,0),colors.HexColor("#0b1b28")),("TEXTCOLOR",(0,0),(-1,0),colors.white)]))
        story.append(bt)
        story += [Spacer(1, 14), Paragraph("Methodology Notes", styles["Heading2"])]
        for x in _report_lines(data)[-5:]:
            story.append(Paragraph(x.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;"), styles["Normal"]))
        doc.build(story)
        return buf.getvalue()
    except Exception:
        return _simple_pdf(_report_lines(data))


@router.get("")
def reports_overview(days: int = Query(30, ge=1, le=3650)):
    return service.overview(days)


@router.get("/pdf")
def reports_pdf(days: int = Query(30, ge=1, le=3650)):
    data = service.overview(days)
    pdf = build_pdf(data)
    filename = f"baby-report-{datetime.now(ET).date().isoformat()}-{days}d.pdf"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
