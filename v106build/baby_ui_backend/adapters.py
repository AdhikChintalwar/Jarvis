from __future__ import annotations
from typing import Any
from .models import *

def g(obj:Any,*names,default=None):
    for n in names:
        if isinstance(obj,dict) and n in obj: return obj[n]
        if hasattr(obj,n): return getattr(obj,n)
    return default

def metric(key,label,abbr,value,definition='',formula=None,inputs=None,status='UNKNOWN',source='Baby deterministic engine',authority='DERIVED',as_of=None,reference=None,interpretation='',threshold=None):
    known=value is not None
    return Metric(key,label,abbr,value,definition=definition,formula=formula,inputs=inputs or {},status=status if known else 'UNKNOWN',interpretation=interpretation,threshold=threshold,provenance=[Provenance(source,authority,as_of,verified=status=='PASS',status=status if known else 'UNKNOWN',reference=reference)])

def report_from_investment_result(symbol:str, result:Any)->ResearchReport:
    """Strict projection of BabyInvestmentSystem output. Missing production packets stay explicit."""
    decision=g(result,'decision',default={}) or {}
    report=g(result,'report','analysis',default={}) or {}
    tech=g(report,'technical',default={}) or {}
    fin=g(report,'financial_health','financials',default={}) or {}
    acct=g(report,'accounting_quality',default={}) or {}
    val=g(report,'valuation',default={}) or {}
    unified=g(report,'unified_risk',default={}) or {}
    legacy_risk=g(report,'risk',default={}) or {}
    validation=g(result,'validation',default={}) or {}
    trade=g(result,'trade_plan','trade',default=None)
    trade=trade if isinstance(trade,dict) else (getattr(trade,'__dict__',{}) if trade is not None else {})
    contract=g(result,'production_contract',default={}) or {}

    decision_state=str(g(decision,'research_state',default='UNKNOWN')).upper()
    decision_score=g(decision,'score')
    confidence=g(decision,'evidence_confidence')
    coverage=g(decision,'evidence_coverage')
    risk_level=str(g(unified,'risk_level',default='UNKNOWN')).upper()
    hard_overrides=g(unified,'hard_overrides',default=[]) or []
    hard=bool(hard_overrides)
    setup=(g(g(trade,'current_setup',default={}) or {},'status',default=None) or g(trade,'status',default='NOT_PRODUCED'))

    stages=[]
    stages.append(ResearchStage('data','Data Collection','PASS',summary='Production StockAnalyzer evidence packet loaded.'))
    stages.append(ResearchStage('financials','Financial Health','PASS' if fin else 'UNKNOWN',score=g(fin,'quality_score','score'),unknowns=list(g(fin,'unknowns',default=[]) or []),metrics=[
      metric('revenue','Revenue',None,g(fin,'revenue',default=g(report,'revenue')),source='SEC/XBRL primary financial evidence',authority='PRIMARY'),
      metric('revenue_growth','Revenue Growth','YoY',g(fin,'revenue_growth'),definition='Revenue growth compared with the corresponding prior period.'),
      metric('net_income','Net Income',None,g(fin,'net_income',default=g(report,'net_income')),source='SEC/XBRL primary financial evidence',authority='PRIMARY'),
      metric('ocf','Operating Cash Flow','OCF',g(fin,'operating_cash_flow',default=g(report,'operating_cash_flow')),source='SEC/XBRL primary financial evidence',authority='PRIMARY'),
      metric('fcf','Free Cash Flow','FCF',g(fin,'free_cash_flow',default=g(report,'free_cash_flow')),formula='FCF = OCF - CapEx',inputs={'OCF':g(fin,'operating_cash_flow',default=g(report,'operating_cash_flow')),'CapEx':g(fin,'capex',default=g(report,'capex'))},source='Baby deterministic calculation from SEC/XBRL',authority='DERIVED'),
      metric('cash','Cash',None,g(fin,'cash',default=g(report,'cash')),source='SEC/XBRL primary financial evidence',authority='PRIMARY'),
      metric('debt','Total Debt',None,g(fin,'debt',default=g(report,'debt')),source='SEC/XBRL primary financial evidence',authority='PRIMARY'),
    ]))
    stages.append(ResearchStage('accounting','Accounting Quality','PASS' if acct else 'UNKNOWN',score=g(acct,'score'),summary=str(g(acct,'summary',default=''))))
    stages.append(ResearchStage('valuation','Valuation','PASS' if val else 'UNKNOWN',score=g(val,'score'),summary=str(g(val,'label','valuation',default=''))))
    stages.append(ResearchStage('technical','Technical Analysis','PASS' if tech else 'UNKNOWN',score=g(tech,'score'),metrics=[
      metric('price','Current Research Price',None,g(tech,'current_price','price',default=g(g(report,'market',default={}) or {},'current_price')),source='Research market snapshot',authority='MARKET'),
      metric('sma20','20-period Simple Moving Average','SMA',g(tech,'sma_20'),formula='SMA20 = mean(last 20 closes)'),
      metric('sma50','50-period Simple Moving Average','SMA',g(tech,'sma_50'),formula='SMA50 = mean(last 50 closes)'),
      metric('sma200','200-period Simple Moving Average','SMA',g(tech,'sma_200'),formula='SMA200 = mean(last 200 closes)'),
      metric('ema20','20-period Exponential Moving Average','EMA',g(tech,'ema_20')),
      metric('rsi14','14-period Relative Strength Index','RSI',g(tech,'rsi_14')),
      metric('atr14','14-period Average True Range','ATR',g(tech,'atr_14')),
      metric('volume','Volume',None,g(tech,'volume')),
      metric('rvol','Relative Volume','RVOL',g(tech,'relative_volume')),
    ]))
    stages.extend([
      ResearchStage('liquidity','Volume & Liquidity','PASS' if legacy_risk else 'UNKNOWN'),
      ResearchStage('sec','SEC / Corporate Events','PASS' if g(report,'sec_event_context','sec_filing_analysis',default=None) else 'UNKNOWN'),
      ResearchStage('macro','Macro / Market Environment','PASS' if g(report,'macro_regime',default=None) else 'UNKNOWN',score=g(g(report,'macro_regime',default={}) or {},'score')),
      ResearchStage('risk','Unified Risk','FAIL' if hard else ('PASS' if unified else 'UNKNOWN'),score=g(unified,'risk_score'),summary=risk_level,negatives=[str(x) for x in hard_overrides]),
      ResearchStage('validation','Independent Verification',str(g(validation,'status',default='UNKNOWN')).upper(),score=g(validation,'score'),summary=f"Coverage {g(validation,'coverage',default='UNKNOWN')}% · Primary evidence remains authoritative; independent sources are cross-checks."),
      ResearchStage('decision','Decision Engine','PASS' if decision_state!='UNKNOWN' else 'FAIL',score=decision_score,summary=decision_state,unknowns=list(g(decision,'unknowns',default=[]) or []),negatives=list(g(decision,'constraints',default=[]) or [])),
      ResearchStage('trade','Trade Plan','PASS' if trade else 'UNKNOWN',summary=str(setup)),
      ResearchStage('portfolio','Portfolio Impact','UNKNOWN'), ResearchStage('history','Historical Validation','UNKNOWN')
    ])
    raw_contract=contract if contract else {'status':'UNKNOWN','reason':'No production contract exported.'}
    return ResearchReport(symbol=symbol,company_name=str(g(report,'company_name',default='')),decision=decision_state,score=decision_score,confidence=confidence,coverage=coverage,risk=risk_level,hard_risk_override=hard,data_integrity=str(g(result,'data_integrity',default='UNKNOWN')).upper(),validation_status=str(g(validation,'status',default='UNKNOWN')).upper(),ai_scoring_authority=float(g(result,'ai_scoring_authority',default=0.0) or 0.0),ai_execution_authority=str(g(result,'ai_execution_authority',default='NONE')),stages=stages,trade_plan=trade,portfolio_impact=g(result,'portfolio_impact',default={}) or {},historical_validation=g(result,'historical_validation',default={}) or {},raw={'production_contract':raw_contract})
