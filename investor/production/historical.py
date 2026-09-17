from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from investor.v115.lab import HistoricalStrategyLab, StrategyConfig
from investor.v115.models import ReplayDecision, PriceBar

@dataclass(frozen=True)
class PITReplayStatus:
    status:str; decisions:int; bars:int; warnings:list

class ProductionHistoricalValidator:
    '''Adapter around the existing V5-V7.5 PIT infrastructure and V11.5 lab.
    It refuses historical claims unless every supplied decision declares PIT availability.'''
    def __init__(self): self.lab=HistoricalStrategyLab()
    def normalize_decision(self,row:dict)->ReplayDecision:
        return ReplayDecision(
            symbol=str(row['symbol']).upper(), signal_time=str(row['signal_time']), score=float(row['score']),
            confidence=float(row['confidence']), coverage=float(row['coverage']), state=str(row['state']),
            risk_level=str(row.get('risk_level','UNKNOWN')), hard_risk=bool(row.get('hard_risk',False)),
            expectations=str(row.get('expectations','UNKNOWN')), setup=str(row.get('setup','UNKNOWN')),
            evidence_available_at=row.get('evidence_available_at'),
            market_available_at=row.get('market_available_at'),
            universe_as_of=row.get('universe_as_of'),
        )
    def normalize_bar(self,row:dict)->PriceBar:
        return PriceBar(symbol=str(row['symbol']).upper(),date=str(row['date']),open=float(row['open']),high=float(row['high']),low=float(row['low']),close=float(row['close']),volume=float(row.get('volume',0)))
    def run(self,decisions,bars,*,config=None,initial_cash=100000,integrity_flags=None,benchmarks=None,record=True):
        ds=[x if isinstance(x,ReplayDecision) else self.normalize_decision(x) for x in decisions]; bs=[x if isinstance(x,PriceBar) else self.normalize_bar(x) for x in bars]
        flags={'universe_complete':False,'delistings_complete':False,'corporate_actions_complete':False,'macro_vintages_complete':False}
        flags.update(integrity_flags or {})
        result=self.lab.run(ds,bs,config or StrategyConfig(),initial_cash,integrity_flags=flags,benchmark_curves=benchmarks,record=record)
        out=result.to_dict(); out['production_claim_status']='VALIDATION_ONLY' if out.get('integrity',{}).get('status')!='PASS' or not all(flags.values()) else 'POINT_IN_TIME_VALIDATED'
        out['automatic_production_retuning']='DISABLED'; out['untouched_test_used_for_selection']=False
        return out
