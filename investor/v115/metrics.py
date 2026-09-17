import math, statistics

def performance(equity, periods_per_year=252):
    if len(equity)<2:return {'status':'INSUFFICIENT_HISTORY'}
    vals=[float(x['equity']) for x in equity]; rets=[vals[i]/vals[i-1]-1 for i in range(1,len(vals)) if vals[i-1]>0]
    total=vals[-1]/vals[0]-1; years=max((len(vals)-1)/periods_per_year,1/periods_per_year)
    cagr=(vals[-1]/vals[0])**(1/years)-1 if vals[0]>0 else None
    vol=statistics.stdev(rets)*math.sqrt(periods_per_year) if len(rets)>1 else 0
    mean=statistics.mean(rets)*periods_per_year if rets else 0
    downside=[r for r in rets if r<0]; dvol=statistics.stdev(downside)*math.sqrt(periods_per_year) if len(downside)>1 else 0
    peak=vals[0]; mdd=0
    for v in vals: peak=max(peak,v); mdd=min(mdd,v/peak-1)
    return {'status':'PASS','total_return_pct':round(total*100,4),'cagr_pct':round(cagr*100,4),'annual_volatility_pct':round(vol*100,4),
            'sharpe':round(mean/vol,4) if vol else None,'sortino':round(mean/dvol,4) if dvol else None,'max_drawdown_pct':round(mdd*100,4),'final_equity':round(vals[-1],2)}

def trade_stats(trades):
    closed=[t for t in trades if t.get('pnl') is not None]; wins=[t for t in closed if t['pnl']>0]; losses=[t for t in closed if t['pnl']<0]
    gp=sum(t['pnl'] for t in wins); gl=-sum(t['pnl'] for t in losses); n=len(closed)
    return {'closed_trades':n,'win_rate_pct':round(100*len(wins)/n,2) if n else None,'profit_factor':round(gp/gl,4) if gl else (None if not gp else float('inf')),
            'expectancy':round(sum(t['pnl'] for t in closed)/n,4) if n else None}
