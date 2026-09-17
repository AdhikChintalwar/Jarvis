from datetime import datetime

def _dt(x):
    if not x:return None
    return datetime.fromisoformat(str(x).replace('Z','+00:00'))

class PointInTimeAudit:
    """Fail-closed PIT audit. Historical evidence must have availability timestamps <= signal time."""
    def audit(self, decisions, *, universe_complete=False, delistings_complete=False,
              corporate_actions_complete=False, macro_vintages_complete=False):
        violations=[]; unknown=[]
        for d in decisions:
            t=_dt(d.signal_time)
            for field in ('evidence_available_at','market_available_at'):
                v=_dt(getattr(d,field,None))
                if v is None: unknown.append({'symbol':d.symbol,'signal_time':d.signal_time,'field':field})
                elif t and v>t: violations.append({'symbol':d.symbol,'signal_time':d.signal_time,'field':field,'available_at':getattr(d,field)})
            if not d.universe_as_of: unknown.append({'symbol':d.symbol,'signal_time':d.signal_time,'field':'universe_as_of'})
            elif t and _dt(d.universe_as_of)>t: violations.append({'symbol':d.symbol,'signal_time':d.signal_time,'field':'universe_as_of','available_at':d.universe_as_of})
        limitations=[]
        for name,val in [('survivorship_universe',universe_complete),('delistings',delistings_complete),('corporate_actions',corporate_actions_complete),('macro_vintages',macro_vintages_complete)]:
            if not val: limitations.append(name.upper()+'_INCOMPLETE')
        status='FAIL' if violations else ('REVIEW' if unknown or limitations else 'PASS')
        return {'status':status,'lookahead_violations':violations,'availability_unknowns':unknown,'limitations':limitations,
                'claim_policy':'Historical performance is not decision-grade when PIT violations exist.',
                'survivorship_status':'COMPLETE' if universe_complete and delistings_complete else 'INCOMPLETE'}
