"""Audit an existing V7 JSON without rerunning SEC or market downloads."""
import argparse,json
from pathlib import Path
import pandas as pd


def main():
    ap=argparse.ArgumentParser();ap.add_argument("report",nargs="?",default="data/v7_real_investment_test.json");ap.add_argument("--output",default="data/v7_5_existing_report_audit.json");a=ap.parse_args()
    d=json.loads(Path(a.report).read_text());curve=pd.DataFrame(d["equity_curve"]);curve.date=pd.to_datetime(curve.date)
    first_signal=min(pd.Timestamp(x["date"]) for x in d["signals"]) if d["signals"] else None
    first_fill=min(pd.Timestamp(x["execution_date"]) for x in d["fills"]) if d["fills"] else None
    start=curve.date.min();end=curve.date.max()
    findings=[]
    if first_fill is not None and first_fill>start:findings.append({"severity":"HIGH","code":"IDLE_PRE_SIGNAL_PERIOD_IN_METRICS","detail":f"Portfolio metric window starts {start.date()} but first fill is {first_fill.date()}; CAGR/volatility/Sharpe include an idle cash period."})
    b=d.get("benchmarks",{})
    if b:findings.append({"severity":"HIGH","code":"BENCHMARK_WINDOW_NOT_PROVEN_ALIGNED","detail":"V7 report stores benchmark metrics but not benchmark curves/aligned dates; relative performance cannot be audited from JSON alone."})
    cal=d.get("calibration",{});bins=cal.get("bins",[])
    for x in bins:
        if int(x.get("n",0))<10:findings.append({"severity":"MEDIUM","code":"SMALL_CALIBRATION_BIN","detail":f"Score bin {x.get('score_bin')} has n={x.get('n')}; do not infer monotonic score skill from it."})
    audit=d.get("audit",{})
    if audit.get("survivorship_status")!="COMPLETE":findings.append({"severity":"HIGH","code":"SURVIVORSHIP_INCOMPLETE","detail":"Fixed current large-cap sample cannot support survivorship-free broad-market performance claims."})
    out={"source_report":a.report,"source_metrics":d.get("metrics",{}),"source_benchmarks":b,"first_signal_date":str(first_signal.date()) if first_signal is not None else None,"first_fill_date":str(first_fill.date()) if first_fill is not None else None,"curve_start":str(start.date()),"curve_end":str(end.date()),"findings":findings,"verdict":"V7_RESULTS_REQUIRE_WINDOW_ALIGNMENT_BEFORE_STRATEGY_CALIBRATION","next_release":"V7.5"}
    p=Path(a.output);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2));print("Saved:",p)
if __name__=="__main__":main()
