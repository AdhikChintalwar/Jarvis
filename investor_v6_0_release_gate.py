import subprocess,sys
tests=[
 "investor_v4_8_4_contract_test.py",
 "investor_v5_0_contract_test.py",
 "investor_v5_5_contract_test.py",
 "investor_v6_0_contract_test.py",
 "investor_v6_0_real_sec_gate.py",
]
for t in tests:
    print("\n>>>",t,flush=True)
    r=subprocess.run([sys.executable,t])
    if r.returncode: raise SystemExit(r.returncode)
print("\nBABY INVESTOR V6.0 RELEASE GATE: PASS")
