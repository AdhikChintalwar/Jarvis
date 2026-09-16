import subprocess,sys
TESTS=["investor_v4_8_4_contract_test.py","investor_v5_0_contract_test.py","investor_v5_5_contract_test.py","investor_v6_0_contract_test.py","investor_v6_5_contract_test.py","investor_v7_0_contract_test.py","investor_v7_5_contract_test.py"]
for t in TESTS:
    print("\n===",t,"===")
    r=subprocess.run([sys.executable,t])
    if r.returncode:raise SystemExit(r.returncode)
print("\nBABY INVESTOR V7.5 RELEASE GATE: PASS")
