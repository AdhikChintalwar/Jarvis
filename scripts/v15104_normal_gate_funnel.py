#!/usr/bin/env python3
from __future__ import annotations

import argparse
import inspect
import json
from collections import Counter
from pathlib import Path

ACTIVE_SETUP = {"AT_PULLBACK_ZONE", "BREAKOUT_TRIGGERED", "SETUP_READY", "ELIGIBLE"}
WAITING_SETUP = {
    "WAIT_FOR_PULLBACK_OR_BREAKOUT", "PULLBACK_RESEARCH_ONLY",
    "BREAKOUT_RESEARCH", "NO_CONFIRMED_FUTURE_RESISTANCE",
    "WAIT_RISK_CONSTRAINED", "UNAVAILABLE", "UNKNOWN",
}

def u(v):
    return str(v or "UNKNOWN").upper()

def n(v):
    try:
        return float(v)
    except Exception:
        return None

def rr(entry, stop, target):
    e,s,t = n(entry),n(stop),n(target)
    if None in (e,s,t) or e <= s:
        return None
    return (t-e)/(e-s)

def load_reports(report_dir):
    rows=[]
    for p in sorted(Path(report_dir).glob("*.json")):
        try:
            d=json.loads(p.read_text())
            if isinstance(d,dict):
                rows.append((p,d))
        except Exception:
            pass
    return rows

def classify_report(p,d):
    trade=d.get("trade_plan") or {}
    cur=trade.get("current_setup") or {}
    pull=trade.get("pullback") or {}
    brk=trade.get("breakout") or {}

    current_status=u(cur.get("status") or trade.get("status"))
    decision=u(d.get("decision"))
    risk=u(d.get("risk"))
    hard=bool(d.get("hard_risk_override"))
    data_integrity=u(d.get("data_integrity"))
    validation=u(d.get("validation_status"))

    active = current_status in ACTIVE_SETUP

    # Determine which plan would matter if active.
    if current_status == "BREAKOUT_TRIGGERED":
        plan=brk
        entry=n(plan.get("trigger") or plan.get("planned_entry"))
    else:
        plan=pull
        entry=n(plan.get("planned_entry"))
    stop=n(plan.get("invalidation"))
    t1=n(plan.get("target_1"))
    t2=n(plan.get("target_2"))
    rr1=rr(entry,stop,t1)
    rr2=rr(entry,stop,t2)

    blockers=[]
    if hard:
        blockers.append("HARD_RISK")
    if risk in {"HIGH","CRITICAL"}:
        blockers.append("RISK_"+risk)
    if current_status == "WAIT_RISK_CONSTRAINED":
        blockers.append("WAIT_RISK_CONSTRAINED")
    elif current_status not in ACTIVE_SETUP:
        blockers.append("NO_ACTIVE_SETUP:"+current_status)
    if active:
        if entry is None: blockers.append("MISSING_ENTRY")
        if stop is None: blockers.append("MISSING_INVALIDATION")
        if t1 is None: blockers.append("MISSING_TARGET_1")
        if t2 is None: blockers.append("MISSING_TARGET_2")
        if rr1 is None or rr1 < 1.0: blockers.append("RR1_BELOW_1")
        if rr2 is None or rr2 < 2.0: blockers.append("RR2_BELOW_2")
    if data_integrity in {"FAIL","INVALID"}:
        blockers.append("DATA_INTEGRITY_"+data_integrity)
    if validation in {"FAIL","INVALID"}:
        blockers.append("VALIDATION_"+validation)

    return {
        "symbol":u(d.get("symbol") or p.stem),
        "decision":decision,
        "score":d.get("score"),
        "risk":risk,
        "hard_risk":hard,
        "data_integrity":data_integrity,
        "validation":validation,
        "current_setup":current_status,
        "active_setup":active,
        "pullback_status":u(pull.get("status")),
        "breakout_status":u(brk.get("status")),
        "entry":entry,
        "stop":stop,
        "target1":t1,
        "target2":t2,
        "rr1":round(rr1,2) if rr1 is not None else None,
        "rr2":round(rr2,2) if rr2 is not None else None,
        "blockers":blockers,
    }

def synthetic_smoke():
    import baby_ui_backend.proposal_service as mod

    candidates=[]
    for name, cls in inspect.getmembers(mod, inspect.isclass):
        if cls.__module__ == mod.__name__ and hasattr(cls, "build"):
            try:
                sig=inspect.signature(cls)
                required=[
                    p for p in sig.parameters.values()
                    if p.name!="self"
                    and p.default is inspect._empty
                    and p.kind in (p.POSITIONAL_ONLY,p.POSITIONAL_OR_KEYWORD)
                ]
                if not required:
                    candidates.append((name,cls))
            except Exception:
                pass

    if not candidates:
        return {"status":"ERROR","reason":"No zero-required-argument proposal service class with build() found."}

    name,Cls=candidates[0]
    svc=Cls()

    quote={
        "price":100.0,"last_price":100.0,"quote_price":100.0,
        "bid":99.95,"ask":100.05,"spread_pct":0.10,
        "age_seconds":1.0,"quote_age_seconds":1.0,
        "timestamp":"2026-09-27T23:00:00+00:00",
        "as_of":"2026-09-27T23:00:00+00:00",
        "provider":"ALPACA_IEX","source":"ALPACA_IEX",
        "quality":"PASS","status":"PASS","execution_grade":True,
    }
    portfolio={
        "account":{"equity":100000.0,"cash":100000.0,"buying_power":100000.0},
        "equity":100000.0,"cash":100000.0,"buying_power":100000.0,
    }

    attempts=[]
    for decision in ("CANDIDATE","STRONG_CANDIDATE","WATCH","BUY"):
        for setup in ("AT_PULLBACK_ZONE","BREAKOUT_TRIGGERED"):
            trade={
                "status":setup,
                "current_setup":{"status":setup,"reason":"Synthetic reachability smoke test."},
                "pullback":{
                    "status":"AT_PULLBACK_ZONE",
                    "entry_low":99.0,"entry_high":101.0,"planned_entry":100.0,
                    "invalidation":95.0,"target_1":105.5,"target_2":111.0,
                    "risk_reward_1":1.1,"risk_reward_2":2.2,
                },
                "breakout":{
                    "status":"BREAKOUT_TRIGGERED",
                    "entry_low":99.5,"entry_high":100.5,"planned_entry":100.0,"trigger":100.0,
                    "invalidation":95.0,"target_1":105.5,"target_2":111.0,
                    "risk_reward_1":1.1,"risk_reward_2":2.2,
                },
                "current_price":100.0,
                "research_state":decision,
                "risk_level":"LOW",
                "hard_risk_override":False,
            }
            research={
                "symbol":"SYNTH","company_name":"Synthetic Reachability Test",
                "decision":decision,"score":80.0,"confidence":90.0,"coverage":95.0,
                "risk":"LOW","hard_risk_override":False,
                "data_integrity":"PASS","validation_status":"PASS",
                "trade_plan":trade,
                "ai_scoring_authority":0.0,"ai_execution_authority":"NONE",
            }
            try:
                r=svc.build("SYNTH",research,quote,portfolio)
                attempts.append({
                    "decision":decision,"setup":setup,
                    "eligible":bool(r.get("eligible")),
                    "status":r.get("status"),
                    "reason":r.get("reason"),
                    "failures":r.get("gate_failures") or r.get("failures") or [],
                    "setup_status":r.get("setup_status"),
                    "quantity_source":r.get("quantity_source"),
                    "real_money_execution":r.get("real_money_execution"),
                })
            except Exception as e:
                attempts.append({
                    "decision":decision,"setup":setup,"eligible":False,
                    "exception":f"{type(e).__name__}: {e}",
                })

    hit=next((x for x in attempts if x.get("eligible")),None)
    return {
        "status":"PASS" if hit else "NO_ELIGIBLE_SYNTHETIC_PATH",
        "service_class":name,
        "eligible_example":hit,
        "attempts":attempts,
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--report-dir",default="data/ui_research")
    ap.add_argument("--json-out",default="/tmp/baby_v15104_gate_funnel.json")
    args=ap.parse_args()

    reports=load_reports(args.report_dir)
    rows=[classify_report(p,d) for p,d in reports]

    setup_counts=Counter(r["current_setup"] for r in rows)
    decision_counts=Counter(r["decision"] for r in rows)
    risk_counts=Counter(r["risk"] for r in rows)
    blocker_counts=Counter(b for r in rows for b in r["blockers"])

    active=[r for r in rows if r["active_setup"]]
    structurally_clean=[
        r for r in active
        if not any(
            b.startswith(("HARD_RISK","RISK_HIGH","RISK_CRITICAL","MISSING_","RR","DATA_INTEGRITY","VALIDATION"))
            for b in r["blockers"]
        )
    ]

    smoke=synthetic_smoke()

    result={
        "reports":len(rows),
        "setup_counts":dict(setup_counts),
        "decision_counts":dict(decision_counts),
        "risk_counts":dict(risk_counts),
        "blocker_counts":dict(blocker_counts),
        "active_setup_count":len(active),
        "structurally_clean_active_setup_count":len(structurally_clean),
        "active_setups":active,
        "synthetic_proposal_reachability":smoke,
        "rows":rows,
        "interpretation":{
            "zero_active_setup_means":"Current saved production research reports never reached an active trade setup before quote/PAPER checks.",
            "synthetic_pass_means":"ProposalService has at least one mechanically reachable eligibility path with a clean synthetic normal-stock setup.",
            "synthetic_fail_means":"The final proposal gate itself may be logically unreachable or requires an input contract not represented by the current smoke test.",
        },
    }
    Path(args.json_out).write_text(json.dumps(result,indent=2,default=str))

    print("=== BABY V15.10.4 NORMAL GATE FUNNEL AUDIT ===")
    print("Reports inspected:",len(rows))
    print("\nCURRENT SETUP STATES")
    for k,v in setup_counts.most_common():
        print(f"  {k:<36} {v}")
    print("\nDECISION STATES")
    for k,v in decision_counts.most_common():
        print(f"  {k:<24} {v}")
    print("\nRISK STATES")
    for k,v in risk_counts.most_common():
        print(f"  {k:<24} {v}")
    print("\nTOP BLOCKERS")
    for k,v in blocker_counts.most_common(20):
        print(f"  {k:<44} {v}")

    print("\nACTIVE SETUPS:",len(active))
    for r in active[:30]:
        print(
            f"  {r['symbol']:<7} decision={r['decision']:<18} risk={r['risk']:<9} "
            f"setup={r['current_setup']:<20} RR1={r['rr1']} RR2={r['rr2']} blockers={r['blockers']}"
        )

    print("\nSTRUCTURALLY CLEAN ACTIVE SETUPS:",len(structurally_clean))

    print("\nSYNTHETIC FINAL-GATE REACHABILITY")
    print("  status :",smoke.get("status"))
    print("  class  :",smoke.get("service_class"))
    if smoke.get("eligible_example"):
        print("  eligible example:",smoke["eligible_example"])
    else:
        for x in smoke.get("attempts",[]):
            print(" ",x)

    print("\nJSON:",args.json_out)
    print("\nIMPORTANT:")
    print("- This audit does NOT relax any gate.")
    print("- Synthetic reachability proves mechanics only, not predictive quality.")
    print("- Real-report funnel shows where actual normal-stock production reports are stopping.")

if __name__=="__main__":
    main()
