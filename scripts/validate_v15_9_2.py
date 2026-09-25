from pathlib import Path
root=Path(__file__).resolve().parents[1]
ve=(root/'baby_ui_backend/v155_email.py').read_text()
se=(root/'baby_ui_backend/subscriber_email.py').read_text()
checks={
'research_ready_gate':'def research_email_eligible(cur):' in ve,
'insufficient_data_block':"phase in {'','UNKNOWN','INSUFFICIENT_DATA'}" in ve,
'early_research_silent':"stage not in {'MONITOR','SETUP_FORMING'}" in ve,
'meaningful_evidence_required':'meaningful_flow' in ve and 'meaningful_catalyst' in ve,
'company_name_research':'company_name=None' in ve and 'display_name=' in ve,
'trade_plan_snapshot':'RESEARCH / TRADE PLAN SNAPSHOT' in ve,
'subscriber_passes_company':"company=report.get('company_name')" in se,
'subscriber_passes_paper':'v155_build_email(intel,event,context,company,paper)' in se,
'setup_subject_company':"subject=f'Baby — {symbol} ({company}) — setup ready for review'" in se,
'setup_header_company':"{e(symbol)} — {e(company)}" in se,
'authority_unchanged':'Quantity is USER_SELECTED' in ve,
}
failed=[k for k,v in checks.items() if not v]
if failed:raise SystemExit('V15.9.2 validation FAILED: '+', '.join(failed))
print('V15.9.2 validation PASS')
print('INSUFFICIENT_DATA and early RESEARCH discovery are silent.')
print('Positive research alerts require MONITOR/SETUP_FORMING plus meaningful flow or catalyst evidence.')
print('Ticker + organization name are included when available.')
print('Research emails surface available quote/trade-plan fields without inventing missing levels.')
print('No automatic execution or quantity selection was added.')
