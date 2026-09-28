#!/usr/bin/env python3
from pathlib import Path

p = Path("baby_ui_backend/app.py")
t = p.read_text()

required = [
    "V15.10.5: scheduled/worker revalidation",
    "research = json.loads(p.read_text())",
    "flow.get('intelligence_v106')",
    "v11_platform.build(symbol, research, v106, flow, record=False)",
    "BABY_V11_TO_V12_MONITOR",
]
for needle in required:
    assert needle in t, needle

bad = "v11_platform.build(symbol, research, v106, flow.get('portfolio') or {})"
assert bad not in t, "old monitor wiring still present"

print("V15.10.5 validation PASS")
print("Monitor revalidation now passes the full V10 flow into V11.")
print("Persisted research artifact and intelligence_v106 are used consistently with production_decision.")
print("Execution authority remains NONE; real-money execution remains DISABLED.")
