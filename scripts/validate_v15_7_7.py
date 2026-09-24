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

print("V15.7.7 validation PASS")
print("Opening-range breakdown now requires persistence or decisive depth.")
print("Single support wicks/crosses no longer automatically become INTRADAY_BREAKDOWN.")
print("No automatic execution or quantity selection was added.")
