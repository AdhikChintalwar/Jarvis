from __future__ import annotations
import json
from pathlib import Path
from .adapters import report_from_investment_result

def export_ui_report(symbol,result,out_dir='data/ui_research'):
    report=report_from_investment_result(symbol,result)
    p=Path(out_dir); p.mkdir(parents=True,exist_ok=True)
    target=p/f'{symbol.upper()}.json'; target.write_text(json.dumps(report.to_dict(),indent=2,default=str)); return target
