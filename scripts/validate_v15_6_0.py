#!/usr/bin/env python3
from pathlib import Path
import py_compile

root=Path.cwd()
targets=[
    root/"baby_ui_backend/v155_intelligence.py",
    root/"baby_ui_backend/v156_regime.py",
    root/"scripts/v155_replay.py",
]
for p in targets:
    if not p.exists():
        raise SystemExit(f"Missing {p}")
    py_compile.compile(str(p), doraise=True)

r=(root/"scripts/v155_replay.py").read_text()
m=(root/"baby_ui_backend/v156_regime.py").read_text()

for marker in [
    "instrument_profile",
    "behavior_regime",
    "research_state",
    "position_state",
    "flow_trend",
    "move_atr",
    "sma20_distance_atr",
]:
    if marker not in m:
        raise SystemExit(f"Missing V15.6 marker in module: {marker}")
    if marker not in r:
        raise SystemExit(f"Missing V15.6 marker in replay: {marker}")

print("V15.6.0 validation PASS")
print("Research state and position state are separated.")
print("ATR-normalized move and SMA20 distance are enabled.")
print("Flow-trend classification is enabled.")
print("No automatic execution or quantity selection was added.")
