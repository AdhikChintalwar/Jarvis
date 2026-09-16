import json
from pathlib import Path

class InvestmentTestReport:
    def save(self,result,path):
        p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text(json.dumps(result,indent=2,default=str))
        return p
