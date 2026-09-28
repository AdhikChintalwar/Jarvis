#!/usr/bin/env python3
import ast
from pathlib import Path

src = Path("baby_ui_backend/app.py").read_text()
tree = ast.parse(src)

fn = next(
    (n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_monitor_decision"),
    None,
)
assert fn is not None, "_monitor_decision missing"

segment = ast.get_source_segment(src, fn) or ""
assert "_v10_build_full_flow" in segment
assert "REPORT_DIR" in segment
assert "intelligence_v106" in segment
assert "v11_platform.build(symbol, research, v106, flow, record=False)" in segment
assert "production_candidate.decision.evaluate" in segment
assert "execution'] = 'NONE'" in segment

for forbidden in (
    "submit_confirmed_order",
    "submit_order(",
    "alpaca_broker.submit",
):
    assert forbidden not in segment, forbidden

print("PASS monitor_uses_full_production_flow")
print("PASS monitor_does_not_submit_orders")
print("V15.10.5 monitor-wiring tests PASS")
