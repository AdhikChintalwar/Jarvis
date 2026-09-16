from pathlib import Path
from baby_ui_backend.control_center import system_status, validation_summary, paper_portfolio, automations, scanner
s=system_status(); assert s['ai_scoring_authority']==0.0 and s['real_money_execution']=='DISABLED'
assert validation_summary()['status'] in {'READY','NOT_AVAILABLE'}
assert paper_portfolio()['real_money_execution']=='DISABLED'
assert automations()['status'] in {'READY','NOT_AVAILABLE'}
assert scanner()['status'] in {'READY','NOT_AVAILABLE'}
app=Path('frontend/src/App.jsx').read_text()
for x in ['Dashboard','Markets','Research','Portfolio','Backtests','Alerts','Automations']: assert x in app
print('BABY V8.2 control-center integration contract: PASS')
print('AI scoring/execution authority: 0%')
print('real-money execution: DISABLED')
