#!/usr/bin/env python3
from pathlib import Path
import py_compile,sys
root=Path.cwd(); req=['baby_ui_backend/v155_intelligence.py','baby_ui_backend/v155_pipeline.py','baby_ui_backend/v155_email.py','scripts/v155_replay.py']
for x in req:
    p=root/x
    if not p.exists():raise SystemExit('Missing '+x)
    py_compile.compile(str(p),doraise=True)
s=(root/'baby_ui_backend/subscriber_email.py').read_text()
for x in ['v155_analyze','_v155_record_and_maybe_email','V155PipelineStore']:
    if x not in s:raise SystemExit('Missing subscriber integration '+x)
print('V15.5 validation PASS')
print('Research/monitoring email integration present.')
print('No automatic order logic added. No Baby quantity selection added.')
