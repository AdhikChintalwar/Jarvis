def _buckets(rows,key,cuts):
    out=[]
    for lo,hi in cuts:
        x=[r for r in rows if r.get(key) is not None and lo<=float(r[key])<hi]
        y=[r.get('forward_return') for r in x if r.get('forward_return') is not None]
        out.append({'range':[lo,hi],'n':len(y),'mean_forward_return_pct':round(sum(y)/len(y)*100,4) if y else None,'positive_rate_pct':round(sum(v>0 for v in y)/len(y)*100,2) if y else None})
    return out

def calibrate(rows):
    return {'score_buckets':_buckets(rows,'score',[(0,35),(35,48),(48,62),(62,75),(75,101)]),
            'confidence_buckets':_buckets(rows,'confidence',[(0,45),(45,60),(60,75),(75,101)]),
            'coverage_buckets':_buckets(rows,'coverage',[(0,50),(50,65),(65,80),(80,101)]),
            'policy':'DIAGNOSTIC_ONLY_NO_AUTOMATIC_RETUNING'}
