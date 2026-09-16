import pandas as pd
from investor.v7 import InvestmentSignal,InvestmentPolicy,RealisticExecutionEngine
from investor.v75 import WindowedInvestmentBacktester,RobustScoreCalibration,V75Audit

def frame(start="2022-01-03",n=900,base=100):
    ix=pd.bdate_range(start,periods=n);return pd.DataFrame({"Open":[base+i*.1 for i in range(n)],"High":[base+1+i*.1 for i in range(n)],"Low":[base-1+i*.1 for i in range(n)],"Close":[base+.2+i*.1 for i in range(n)],"Volume":[1_000_000]*n},index=ix)

def main():
    h=frame();start="2023-01-03";end="2024-12-31";sigdate="2023-06-30"
    s=[InvestmentSignal(sigdate,"AAA",70,"CANDIDATE",80,90,"LOW",False,{})]
    p=InvestmentPolicy(min_score=60,max_position_weight=1.0);e=RealisticExecutionEngine(slippage_bps=5)
    curve,fills,m=WindowedInvestmentBacktester(p,e).run({"AAA":h},s,100000,start,end)
    assert curve[0]["date"]==start,curve[0]
    assert fills and fills[0]["execution_date"]>sigdate
    assert m["actual_start"]==start
    c=RobustScoreCalibration().analyze(s,{"AAA":h});assert c["observations"]==1
    a=V75Audit().build(requested_start=start,requested_end=end,curve=curve,signals=s,universe_size=1)
    assert "PORTFOLIO_CURVE_PRECEDES_REQUESTED_START" not in a["integrity_issues"]
    print("V7.5 CONTRACT: PASS")
if __name__=="__main__":main()
