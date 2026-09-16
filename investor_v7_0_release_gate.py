import subprocess,sys
tests=["investor_v6_5_contract_test.py","investor_v7_0_contract_test.py"]
for t in tests:
    print("\n>>>",t,flush=True)
    r=subprocess.run([sys.executable,t])
    if r.returncode:raise SystemExit(r.returncode)
print("\nBABY INVESTOR V7.0 CODE GATE: PASS")
print("Run actual investment simulation separately:")
print("python investor_v7_0_real_investment_test.py --start 2023-01-03 --end 2025-12-31 --rebalance M")
