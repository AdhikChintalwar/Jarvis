from dataclasses import dataclass, asdict
from typing import Optional, Any

@dataclass(frozen=True)
class ReplayDecision:
    symbol:str; signal_time:str; score:float; confidence:float; coverage:float; state:str
    expectations:str='UNKNOWN'; risk_level:str='UNKNOWN'; hard_risk:bool=False
    setup:str='NONE'; bull_weight:float=0; bear_weight:float=0
    evidence_available_at:Optional[str]=None; market_available_at:Optional[str]=None
    universe_as_of:Optional[str]=None; payload_hash:Optional[str]=None

@dataclass(frozen=True)
class PriceBar:
    symbol:str; date:str; open:float; high:float; low:float; close:float; volume:float=0

@dataclass
class ExperimentResult:
    experiment_id:str; config:dict; metrics:dict; benchmarks:dict; calibration:dict
    walk_forward:dict; integrity:dict; trades:list; equity_curve:list; warnings:list
    schema_version:str='11.5'
    def to_dict(self): return asdict(self)
