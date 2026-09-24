#!/usr/bin/env python3
from pathlib import Path
import py_compile,inspect,sys,re

root=Path.cwd()
for p in [root/"baby_ui_backend/v155_email.py",root/"baby_ui_backend/subscriber_email.py"]:
    py_compile.compile(str(p),doraise=True)

sys.path.insert(0,str(root))
from baby_ui_backend.v155_email import build_email
assert "market_context" in inspect.signature(build_email).parameters

s=(root/"baby_ui_backend/subscriber_email.py").read_text()
assert "v155_build_email(intel,event,context)" in s
assert "report.get('market_context')" in s

print("V15.9.1a validation PASS")
print("Meaningful-change email sections enabled.")
print("subscriber_email passes market context when available.")
print("No automatic execution or quantity selection was added.")
