class V75Audit:
    def build(self,*,requested_start,requested_end,curve,signals,universe_size,point_in_time_sec=True,point_in_time_macro=True):
        first=curve[0]["date"] if curve else None;last=curve[-1]["date"] if curve else None
        issues=[]
        if first and str(first)<str(requested_start):issues.append("PORTFOLIO_CURVE_PRECEDES_REQUESTED_START")
        if not signals:issues.append("NO_SIGNALS")
        return {"release":"7.5","test_type":"ACTUAL_HISTORICAL_INVESTMENT_SIMULATION",
          "requested_start":str(requested_start),"requested_end":str(requested_end),"actual_curve_start":first,"actual_curve_end":last,
          "universe_size":int(universe_size),"universe_method":"fixed_current_large-cap sample","survivorship_status":"INCOMPLETE",
          "point_in_time_sec":bool(point_in_time_sec),"point_in_time_macro":bool(point_in_time_macro),
          "market_source":"Yahoo/yfinance SECONDARY_PROTOTYPE","execution":"signal after close T -> next available trading bar OPEN",
          "corporate_action_mode":"auto_adjusted Yahoo history; prototype limitation","ai_scoring_authority":0.0,"ai_execution_authority":0.0,
          "real_money_execution":"DISABLED","integrity_issues":issues,
          "claim_status":"BOUNDED_RESEARCH_TEST_ONLY",
          "warning":"Not a survivorship-free whole-market track record. Calibration and attribution are descriptive, not evidence to optimize production weights without independent/OOS confirmation."}
