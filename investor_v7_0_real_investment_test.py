import argparse,json
from pathlib import Path
from datetime import timedelta
import pandas as pd
import yfinance as yf
from investor.v7 import InvestmentSignal,InvestmentPolicy,RealisticExecutionEngine,InvestmentBacktester,BenchmarkSuite,ScoreCalibration,StrategyAttribution,InvestmentTestReport
from investor.v65 import BabyHistoricalValidationPlatform

DEFAULT={"AAPL":"320193","MSFT":"789019","NVDA":"1045810","AMZN":"1018724","GOOGL":"1652044",
         "META":"1326801","JPM":"19617","JNJ":"200406","XOM":"34088","WMT":"104169"}

def dl(symbol,start,end):
    x=yf.download(symbol,start=(pd.Timestamp(start)-pd.Timedelta(days=400)).date().isoformat(),
                  end=(pd.Timestamp(end)+pd.Timedelta(days=2)).date().isoformat(),
                  auto_adjust=True,actions=False,progress=False,threads=False)
    if isinstance(x.columns,pd.MultiIndex):
        x=x.xs(symbol,axis=1,level=1) if symbol in x.columns.get_level_values(1) else x.droplevel(1,axis=1)
    x.index=pd.to_datetime(x.index).tz_localize(None)
    return x

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--start",default="2023-01-03");ap.add_argument("--end",default="2025-12-31")
    ap.add_argument("--rebalance",default="M",choices=["W","M","Q"])
    ap.add_argument("--cash",type=float,default=100000)
    ap.add_argument("--output",default="data/v7_real_investment_test.json")
    a=ap.parse_args()
    universe=DEFAULT
    prices={s:dl(s,a.start,a.end) for s in universe}
    spy=dl("SPY",a.start,a.end); qqq=dl("QQQ",a.start,a.end)
    calendar=spy.loc[(spy.index>=a.start)&(spy.index<=a.end)].index
    freq={"W":"W-FRI","M":"ME","Q":"QE"}[a.rebalance]
    schedule=pd.Series(calendar,index=calendar).resample(freq).last().dropna().tolist()
    platform=BabyHistoricalValidationPlatform()
    signals=[]
    print(f"Baby V7 actual investment test: {a.start} -> {a.end}; {len(universe)} symbols; {len(schedule)} rebalances")
    for n,date in enumerate(schedule,1):
        print(f"[{n}/{len(schedule)}] {date.date()}")
        asof=date.strftime("%Y-%m-%d")+"T23:59:59+00:00"
        for sym,cik in universe.items():
            h=prices[sym].loc[prices[sym].index<=date]
            b=spy.loc[spy.index<=date]
            if len(h)<210:continue
            try:
                r=platform.research(sym,cik,asof,h,b)
                d=r["decision"];risk=d["report"]["unified_risk"]
                signals.append(InvestmentSignal(str(date.date()),sym,float(d["score"]),
                    d["research_state"],float(d["evidence_confidence"]),float(d["evidence_coverage"]),
                    str(risk["risk_level"]),bool(risk.get("hard_override",False)),
                    {"macro_as_of":r["macro"]["as_of"],"market_as_of":r["market"].as_of}))
            except Exception as e:
                print("  SKIP",sym,type(e).__name__,str(e)[:100])
    policy=InvestmentPolicy(min_score=60,min_confidence=40,min_coverage=70,max_positions=10,max_position_weight=.10)
    execution=RealisticExecutionEngine(slippage_bps=5,commission=0,max_volume_participation=.02)
    curve,fills,metrics=InvestmentBacktester(policy,execution).run(prices,signals,a.cash)
    benchmarks=BenchmarkSuite().evaluate({"SPY":spy,"QQQ":qqq},a.start,a.end,a.cash)
    calibration=ScoreCalibration().analyze(signals,prices)
    attribution=StrategyAttribution().analyze(signals,prices)
    audit={"test_type":"ACTUAL_HISTORICAL_INVESTMENT_SIMULATION",
      "universe_size":len(universe),"universe_method":"fixed_current_large-cap_sample",
      "survivorship_status":"INCOMPLETE","point_in_time_sec":True,"point_in_time_macro":True,
      "market_source":"Yahoo/yfinance secondary/prototype","execution":"next trading bar OPEN",
      "slippage_bps":5,"max_volume_participation":.02,
      "ai_scoring_authority":0.0,"ai_execution_authority":0.0,
      "real_money_execution":"DISABLED",
      "warning":"This bounded sample is for strategy testing, not a survivorship-free whole-market performance claim."}
    result={"metrics":metrics,"benchmarks":benchmarks,"calibration":calibration,
            "attribution":attribution,"audit":audit,"signals":[s.__dict__ for s in signals],
            "fills":fills,"equity_curve":curve}
    InvestmentTestReport().save(result,a.output)
    print("\n=== BABY V7 INVESTMENT TEST ===")
    print("Final equity:",round(metrics["final_equity"],2))
    print("Total return:",round(metrics.get("total_return",0)*100,2),"%")
    print("CAGR:",round(metrics.get("cagr",0)*100,2),"%")
    print("Sharpe:",metrics.get("sharpe"))
    print("Max drawdown:",round(metrics.get("max_drawdown",0)*100,2),"%")
    print("Fills:",metrics["fills"])
    for k,v in benchmarks.items():print(k,"return:",round(v["total_return"]*100,2),"%","CAGR:",round(v["cagr"]*100,2),"%")
    print("Survivorship:",audit["survivorship_status"])
    print("Report:",a.output)
if __name__=="__main__":main()
