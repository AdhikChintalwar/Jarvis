class V6Audit:
    def build(self,*,snapshots,decisions,backtest,oos=None,universe_coverage=None):
        blocked=sum(len(s.provenance.get("blocked_future_evidence",[])) for s in snapshots)
        missing=sum(1 for s in snapshots if not s.evidence)
        uc=universe_coverage
        survivorship="VERIFIED" if uc is not None and uc>=.99 else "INCOMPLETE"
        return {
          "schema_version":"6.0",
          "snapshots":len(snapshots),"decisions":len(decisions),
          "blocked_future_evidence":blocked,"empty_snapshots":missing,
          "lookahead_violations":backtest.audit.lookahead_violations,
          "point_in_time_fundamentals":backtest.audit.point_in_time_fundamentals,
          "point_in_time_universe":backtest.audit.point_in_time_universe,
          "universe_coverage":uc,"survivorship_status":survivorship,
          "oos":oos or {"status":"NOT_RUN"},
          "ai_scoring_authority":0.0,"ai_execution_authority":0.0,
          "real_money_execution":"DISABLED",
          "status":"PASS" if backtest.audit.lookahead_violations==0 else "FAIL"
        }
