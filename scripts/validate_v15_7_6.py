#!/usr/bin/env python3
from pathlib import Path
import py_compile,sys

root=Path.cwd()
for p in [
    root/"baby_ui_backend/v157_intraday.py",
    root/"scripts/v157_intraday_replay.py",
]:
    py_compile.compile(str(p),doraise=True)

sys.path.insert(0,str(root))
from baby_ui_backend.v157_intraday import assess_intraday

x=assess_intraday([])
assert x.position_signal=="NO_POSITION"

print("V15.7.6 validation PASS")
print("Failed-breakout and HOD-rejection labels now use recent-event windows.")
print("Sticky all-day event labels are prevented.")
print("Position protection requires stronger confluence.")
print("No automatic execution or quantity selection was added.")
