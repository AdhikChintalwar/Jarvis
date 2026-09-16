import argparse
from dataclasses import asdict,is_dataclass
from investor import StockAnalyzer, BabyInvestmentSystem
from investor.providers.yahoo_provider import YahooFinanceProvider

def show(x): return asdict(x) if is_dataclass(x) else x
p=argparse.ArgumentParser();p.add_argument('symbols',nargs='*',default=['AAPL','SLDE','CRWD']);p.add_argument('--account',type=float,default=None);a=p.parse_args()
provider=YahooFinanceProvider();system=BabyInvestmentSystem()
print('='*100);print('BABY INVESTOR V4.6.2 — DETERMINISTIC DECISION + VALIDATION + TRADE PLAN');print('='*100)
for symbol in a.symbols:
    print('\n'+'-'*100);print(symbol)
    report=StockAnalyzer().analyze(symbol)
    history=provider.get_history(symbol,period='1y',interval='1d')
    result=system.evaluate(report,history,account_size=a.account)
    d=result.decision;v=result.validation;t=result.trade_plan or {}
    print('Decision score       :',d['score'])
    print('Evidence confidence  :',d['evidence_confidence'])
    print('Evidence coverage    :',d['evidence_coverage'])
    print('Research state       :',d['research_state'])
    print('Constraints          :',d['constraints'])
    print('Validation           :',v['status'],v['score'])
    print('Validation P/R/F/U   :',v['checks_passed'],v['checks_review'],v['checks_failed'],v['checks_unknown'])
    print('Validation audit:')
    for c in v['checks']:
        print('  ',c['status'],c['name'],'observed=',c['observed'],'reference=',c['reference'],'diff%=',c['difference_pct'],'tol%=',c['tolerance_pct'])
        if c.get('note'): print('     ',c['note'])
    print('AI scoring authority :',result.ai_scoring_authority)
    print('AI role              :',result.ai_role)
    print('Execution authority  :',result.execution_authority)
    if t:
        print('Trade setup          :',t['status'])
        print('Current price        :',t['current_price'])
        if t['current_price'] is None: raise AssertionError(f'{symbol}: valid history produced null current_price')
        print('Entry zone           :',t['entry_low'],'-',t['entry_high'])
        print('Breakout trigger     :',t['breakout_trigger'])
        print('Invalidation         :',t['invalidation'])
        print('Targets              :',t['target_1'],t['target_2'])
        print('Risk/reward          :',t['risk_reward_1'],t['risk_reward_2'])
        if t['planned_entry'] is not None and t['invalidation'] is not None:
            assert t['invalidation'] < t['planned_entry'], f'{symbol}: invalidation must be below entry'
        if t['target_1'] is not None and t['planned_entry'] is not None:
            assert t['target_1'] > t['planned_entry'], f'{symbol}: target 1 must be above entry'
        if t['breakout_trigger'] is not None:
            assert t['breakout_trigger'] > 0, f'{symbol}: breakout trigger invalid'
        print('Valuation context    :',t['valuation_context'])
        print('Risk level           :',t['risk_level'])
        if t['position']: print('Risk-sized position  :',t['position'])
print('\nRESULT: PASS')
