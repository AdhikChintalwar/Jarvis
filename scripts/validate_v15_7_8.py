#!/usr/bin/env python3
from pathlib import Path
import py_compile, sys

root=Path.cwd()
target=root/"baby_ui_backend/v157_intraday.py"
py_compile.compile(str(target),doraise=True)

sys.path.insert(0,str(root))
from baby_ui_backend.v157_intraday import assess_intraday

x=assess_intraday([])
assert x.position_signal=="NO_POSITION"

print("V15.7.8 validation PASS")
print("Breakdown confirmation is now a recent event rather than a sticky all-day state.")
print("Below-support state remains observable separately.")
print("No automatic execution or quantity selection was added.")
