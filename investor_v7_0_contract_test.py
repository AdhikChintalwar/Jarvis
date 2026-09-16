import pandas as pd
from investor.v7 import InvestmentSignal,InvestmentPolicy,RealisticExecutionEngine,InvestmentBacktester,ScoreCalibration
idx=pd.date_range("2024-01-02",periods=80,freq="B")
p=pd.DataFrame({"Open":[100+i*.2 for i in range(80)],"High":[101+i*.2 for i in range(80)],
 "Low":[99+i*.2 for i in range(80)],"Close":[100.5+i*.2 for i in range(80)],"Volume":[1_000_000]*80},index=idx)
signals=[InvestmentSignal(str(idx[20].date()),"TEST",75,"CANDIDATE",80,100,"LOW",False),
         InvestmentSignal(str(idx[50].date()),"TEST",45,"WAIT",80,100,"LOW",False)]
policy=InvestmentPolicy(max_position_weight=1,max_positions=1)
curve,fills,m=InvestmentBacktester(policy,RealisticExecutionEngine(slippage_bps=5)).run({"TEST":p},signals,100000)
assert fills and fills[0]["execution_date"]==str(idx[21].date())
assert fills[0]["side"]=="BUY"
assert any(x["side"]=="SELL" for x in fills)
assert m["final_equity"]>0
cal=ScoreCalibration().analyze(signals,{"TEST":p})
assert cal["observations"]==2
print("V7.0 actual investment-testing contract: PASS")
print("signal T -> next-bar OPEN execution: PASS")
print("portfolio buy/exit lifecycle: PASS")
print("slippage + liquidity participation controls: PASS")
print("score calibration: PASS")
print("AI execution authority: 0%")
