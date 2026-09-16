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
    """Compatibility adapter. It only exposes fields that actually exist; missing stays UNKNOWN."""
    decision=g(result,'decision',default={}); report=g(result,'report','analysis',default=result)
    tech=g(report,'technical',default={}); fin=g(report,'financial_health','financials',default={}); acct=g(report,'accounting_quality',default={}); val=g(report,'valuation',default={}); risk=g(report,'unified_risk','risk',default={}); validation=g(result,'validation',default={}); trade=g(result,'trade','trade_plan',default={})
    stages=[]
    stages.append(ResearchStage('data','Data Collection','PASS',summary='Primary and derived evidence made available to the research pipeline.'))
    stages.append(ResearchStage('financials','Financial Health','PASS' if fin else 'UNKNOWN',score=g(fin,'score'),metrics=[
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
      metric('price','Current Research Price',None,g(tech,'current_price','price',default=g(report,'current_price')),source='Research market snapshot',authority='MARKET'),
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
      ResearchStage('liquidity','Volume & Liquidity','UNKNOWN'), ResearchStage('sec','SEC / Corporate Events','UNKNOWN'),
      ResearchStage('macro','Macro / Market Environment','UNKNOWN'),
      ResearchStage('risk','Unified Risk','FAIL' if g(risk,'hard_override',default=g(result,'hard_risk_override',default=False)) else ('PASS' if risk else 'UNKNOWN'),score=g(risk,'score'),summary=str(g(risk,'level','risk_level',default=g(decision,'risk',default='UNKNOWN')))),
      ResearchStage('validation','Independent Verification',str(g(validation,'status',default='UNKNOWN')).upper(),score=g(validation,'score'),summary='Primary evidence remains authoritative; independent sources are cross-checks.'),
      ResearchStage('decision','Decision Engine','PASS' if decision else 'UNKNOWN',score=g(decision,'score'),summary=str(g(decision,'state','decision',default='UNKNOWN'))),
      ResearchStage('trade','Trade Plan','PASS' if trade else 'UNKNOWN',summary=str(g(trade,'setup','state',default=''))),
      ResearchStage('portfolio','Portfolio Impact','UNKNOWN'), ResearchStage('history','Historical Validation','UNKNOWN')
    ])
    return ResearchReport(symbol=symbol,company_name=str(g(report,'company_name',default='')),decision=str(g(decision,'state','decision',default=g(result,'decision_state',default='UNKNOWN'))),score=g(decision,'score',default=g(result,'score')),confidence=g(decision,'confidence',default=g(result,'confidence')),coverage=g(decision,'coverage',default=g(result,'coverage')),risk=str(g(risk,'level','risk_level',default=g(result,'risk',default='UNKNOWN'))),hard_risk_override=bool(g(risk,'hard_override',default=g(result,'hard_risk_override',default=False))),data_integrity=str(g(result,'data_integrity',default='UNKNOWN')).upper(),validation_status=str(g(validation,'status',default='UNKNOWN')).upper(),ai_scoring_authority=float(g(result,'ai_scoring_authority',default=0.0) or 0.0),ai_execution_authority=str(g(result,'ai_execution_authority',default='NONE')),stages=stages,trade_plan=trade if isinstance(trade,dict) else getattr(trade,'__dict__',{}),portfolio_impact=g(result,'portfolio_impact',default={}) or {},historical_validation=g(result,'historical_validation',default={}) or {})
