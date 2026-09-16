import pandas as pd
class HistoricalMarketReplay:
    def slice_as_of(self,history,as_of,lookback=252):
        h=history.copy().sort_index()
        t=pd.Timestamp(as_of)
        if t.tzinfo is not None and getattr(h.index,"tz",None) is None: t=t.tz_localize(None)
        h=h.loc[h.index<=t]
        return h.tail(lookback)
