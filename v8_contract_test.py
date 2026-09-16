from baby_ui_backend.adapters import report_from_investment_result
from baby_ui_backend.glossary import GLOSSARY
r=report_from_investment_result('TEST',{'decision':{'state':'WATCH','score':71,'confidence':80,'coverage':95},'report':{'technical':{'current_price':100,'sma_20':95,'rsi_14':60},'financial_health':{'revenue':1_000_000,'operating_cash_flow':100_000,'capex':20_000,'free_cash_flow':80_000}},'validation':{'status':'REVIEW'}})
assert r.ai_scoring_authority==0.0
assert r.ai_execution_authority=='NONE'
assert len(r.stages)>=14
assert GLOSSARY['RSI']['name']=='Relative Strength Index'
tech=next(s for s in r.stages if s.id=='technical')
assert next(m for m in tech.metrics if m.key=='rsi14').value==60
print('BABY V8 UI contract: PASS')
print('stages:',len(r.stages),'AI authority:',r.ai_scoring_authority,'execution:',r.ai_execution_authority)
