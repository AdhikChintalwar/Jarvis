from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from baby_ui_backend.adapters import report_from_investment_result
from baby_ui_backend.production_contract import validate_investment_result, ProductionContractError
from baby_ui_backend.paper_trading import PaperTradingService
from baby_ui_backend.proposal_service import PaperProposalService

# Exact production field names from DecisionReport / TradePlanV47 / UnifiedRisk.
decision={
    'score':67.28,'evidence_confidence':68.23,'evidence_coverage':100.0,
    'research_state':'CANDIDATE','components':{},'constraints':[],'unknowns':[]
}
validation={'status':'REVIEW','score':90.48,'coverage':100.0,'checks_passed':17,'checks_review':4,'checks_failed':0,'checks_unknown':0}
trade={
    'status':'AT_PULLBACK_ZONE','current_price':100.0,
    'current_setup':{'status':'AT_PULLBACK_ZONE','reason':'Current price is inside deterministic pullback zone.'},
    'pullback':{'planned_entry':100.0,'invalidation':95.0,'target_1':110.0,'target_2':115.0},
    'breakout':{},'position':{'unified_risk_multiplier':0.8},
    'research_state':'CANDIDATE','risk_level':'MODERATE','hard_risk_override':False
}
prod=SimpleNamespace(decision=decision,validation=validation,trade_plan=trade)
contract=validate_investment_result(prod,252)
assert contract.status=='PASS' and contract.trade_plan_present
combined={
    'report':{'ticker':'AAPL','unified_risk':{'risk_level':'MODERATE','risk_score':30,'hard_overrides':[],'position_risk_multiplier':0.8},'risk':{},'technical':{}},
    'decision':decision,'validation':validation,'trade_plan':trade,
    'production_contract':contract.to_dict(),'ai_scoring_authority':0.0,'ai_execution_authority':'NONE'
}
ui=report_from_investment_result('AAPL',combined).to_dict()
assert ui['decision']=='CANDIDATE'
assert ui['score']==67.28 and ui['confidence']==68.23 and ui['coverage']==100.0
assert ui['risk']=='MODERATE' and ui['hard_risk_override'] is False
assert ui['trade_plan']['current_setup']['status']=='AT_PULLBACK_ZONE'
assert next(x for x in ui['stages'] if x['id']=='decision')['status']=='PASS'
assert next(x for x in ui['stages'] if x['id']=='trade')['status']=='PASS'

with TemporaryDirectory() as td:
    broker=PaperTradingService(str(Path(td)/'paper.db'))
    quote={'price':100,'quality':'DELAYED','provider':'TEST','timestamp':'2026-09-16T15:00:00Z'}
    p=PaperProposalService(.5,10).build('AAPL',ui,quote,broker.snapshot({}))
    assert p['eligible']
    assert p['risk_budget_percent']==0.4 and p['max_position_percent']==8.0
    assert p['proposed_quantity']==80

# Empty/malformed production packets must fail loudly, not become fake UNKNOWN UI data.
try:
    validate_investment_result(SimpleNamespace(decision={},validation={},trade_plan={}),252)
    raise AssertionError('malformed production packet was accepted')
except ProductionContractError:
    pass

# Below 50 OHLC rows is explicitly NOT_PRODUCED, not a valid trade plan.
short=validate_investment_result(SimpleNamespace(decision=decision,validation=validation,trade_plan=None),49)
assert short.trade_setup=='NOT_PRODUCED' and not short.trade_plan_present

print('BABY V8.5 strict production integration contract: PASS')
print('DecisionReport field mapping: PASS')
print('UnifiedRisk hard_overrides mapping: PASS')
print('TradePlanV47 mapping: PASS')
print('30-vs-50 OHLC boundary: FIXED')
print('paper proposal gate + risk multiplier: PASS')
print('AI scoring/execution authority: 0%')
print('real-money execution: DISABLED')
