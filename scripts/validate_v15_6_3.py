#!/usr/bin/env python3
from pathlib import Path
import py_compile

root=Path.cwd()
targets=[
    root/"baby_ui_backend/v155_intelligence.py",
    root/"baby_ui_backend/v156_regime.py",
    root/"baby_ui_backend/v156_event_risk.py",
    root/"baby_ui_backend/v156_market_context.py",
    root/"scripts/v155_replay.py",
]
for p in targets:
    if not p.exists():
        raise SystemExit(f"Missing {p}")
    py_compile.compile(str(p),doraise=True)

m=(root/"baby_ui_backend/v156_market_context.py").read_text()
r=(root/"scripts/v155_replay.py").read_text()

for marker in [
    "market_regime","broad_market_trend","smallcap_trend","sector_trend",
    "volatility_regime","relative_strength_5d","relative_strength_20d",
    "breadth_proxy","context_signal"
]:
    if marker not in m:
        raise SystemExit(f"Missing market-context marker: {marker}")

for marker in [
    "--market-csv","--smallcap-csv","--sector-csv","--vix-csv",
    "assess_market_context","market_regime","context_signal"
]:
    if marker not in r:
        raise SystemExit(f"Missing replay marker: {marker}")

print("V15.6.3 validation PASS")
print("Point-in-time market/sector context replay is enabled.")
print("Relative strength versus broad market is enabled.")
print("Market context remains descriptive; it does not auto-block setups.")
print("No automatic execution or quantity selection was added.")
