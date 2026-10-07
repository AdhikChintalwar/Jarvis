import argparse,json
from baby_ui_backend.v1514_gate_audit import GateAuditService
p=argparse.ArgumentParser();p.add_argument('--days',type=int,default=30);p.add_argument('--symbol');a=p.parse_args();s=GateAuditService();print(json.dumps(s.symbol(a.symbol,a.days) if a.symbol else s.overview(a.days),indent=2,default=str))
