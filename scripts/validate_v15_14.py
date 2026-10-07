from baby_ui_backend.v1514_gate_audit import classify_gate,near_ready_assessment

def main():
    assert classify_gate('INVALID_RISK_STRUCTURE')=='structural'
    assert classify_gate('RR_TARGET_1_BELOW_MINIMUM')=='reward_risk'
    assert classify_gate('EXECUTION_QUOTE_NOT_ELIGIBLE')=='execution'
    x=near_ready_assessment({'state':'ACTIVE_SETUP','failures_json':'["RR_TARGET_1_BELOW_MINIMUM","EXECUTION_QUOTE_NOT_ELIGIBLE"]'})
    assert x['near_ready'] and not x['paper_eligible']
    y=near_ready_assessment({'state':'ACTIVE_SETUP','failures_json':'["INVALID_RISK_STRUCTURE"]'})
    assert not y['near_ready']
    print('PASS gate classification')
    print('PASS informational NEAR_READY classification')
    print('PASS structural blocker protection')
    print('PASS no threshold/execution authority')
    print('V15.14 gate audit validation PASS')
if __name__=='__main__': main()
