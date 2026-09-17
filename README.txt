JARVIS V12 — V11 -> V12 BRIDGE TEST PATCH
===========================================

Run everything from the root of your "Jarvis voice" project while (.venv) is active.

1. CREATE A GIT CHECKPOINT NOW

   git status
   git add -A
   git commit -m "V12 production guardrails validated"

   If Git says there is nothing to commit, that is fine.

2. APPLY THE PATCH

   From the Jarvis project root, run:

   python /path/to/add_v12_bridge_contract_test.py

   The script:
   - edits production_candidate_contract_test.py
   - inserts the bridge test immediately BEFORE the ETF test
   - creates:
     production_candidate_contract_test.py.before_bridge_test.bak

3. RUN TESTS

   python -m py_compile investor/production/platform.py
   python production_candidate_contract_test.py

   Expected result includes:

   BABY PRODUCTION CANDIDATE: PASS

4. IF IT PASSES, CREATE THE NEXT GIT CHECKPOINT

   git status
   git diff
   git add investor/production/platform.py production_candidate_contract_test.py
   git commit -m "Add V11 to V12 production decision bridge"

5. PUSH LATER

   A git commit is only a local checkpoint.
   Do not run git push unless you intentionally want these commits on the remote.

   Recommended: push after the PASS bridge test, BLOCKED bridge test,
   and production health check all pass.

6. ROLLBACK

   Restore the pre-patch test file:
   cp production_candidate_contract_test.py.before_bridge_test.bak production_candidate_contract_test.py

IMPORTANT:
Do not call any Alpaca real-order endpoint while developing this bridge.
V12 should remain proposal/audit-only with real-money execution DISABLED.
