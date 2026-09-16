from dataclasses import dataclass,field,asdict
from typing import Optional,Dict,List,Any

@dataclass
class InvestmentSignal:
    date:str
    symbol:str
    score:float
    state:str
    confidence:float
    coverage:float
    risk_level:str="UNKNOWN"
    hard_override:bool=False
    metadata:Dict[str,Any]=field(default_factory=dict)

@dataclass
class Fill:
    signal_date:str
    execution_date:str
    symbol:str
    side:str
    shares:float
    price:float
    notional:float
    fee:float
    slippage:float
    reason:str

@dataclass
class PortfolioPoint:
    date:str
    equity:float
    cash:float
    gross_exposure:float
    positions:int

@dataclass
class InvestmentTestResult:
    initial_cash:float
    final_equity:float
    equity_curve:List[Dict[str,Any]]
    fills:List[Dict[str,Any]]
    metrics:Dict[str,Any]
    benchmark_metrics:Dict[str,Any]
    calibration:Dict[str,Any]
    attribution:Dict[str,Any]
    audit:Dict[str,Any]
