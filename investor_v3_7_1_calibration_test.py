import sys, types
yf=types.ModuleType("yfinance"); yf.Ticker=lambda *a,**k:None; yf.download=lambda *a,**k:None
sys.modules.setdefault("yfinance",yf)

from investor.accounting_quality import AccountingQualityEngine

def vm(v, confidence=.85):
    return {"value":v,"status":"PRIMARY_ONLY","confidence":confidence,"source":"SEC_XBRL","period":"2025-12-31"}

def primary(net_income=100., periods=2):
    hist=[]
    for i in range(periods):
        hist.append({
            "period_end":f"{2024-periods+i+1}-12-31",
            "operating_margin":.10+.02*i,
            "net_margin":.07+.02*i,
            "free_cash_flow_margin":.08+.02*i,
            "weighted_average_diluted_shares":100.-2*i,
        })
    return {
        "verified_financials":{
            "revenue":vm(1000.),"net_income":vm(net_income),
            "operating_cash_flow":vm(140.),"free_cash_flow":vm(110.),
            "cash":vm(300.),"debt":vm(100.),"shares_change_yoy":vm(-.05),
        },
        "annual_history":{"periods":hist},
    }

# Shallow but strong evidence must not saturate at 100.
strong2=AccountingQualityEngine().analyze(primary(periods=2))
assert strong2.score < 100
assert strong2.score <= 90
assert strong2.history_periods == 2
assert strong2.history_confidence == 55.0

# Five periods should receive stronger trend authority/depth.
strong5=AccountingQualityEngine().analyze(primary(periods=5))
assert strong5.history_periods == 5
assert strong5.history_confidence == 90.0
assert strong5.confidence >= strong2.confidence

# Negative earnings: cash-conversion ratio is N.M., never a misleading negative number.
loss=AccountingQualityEngine().analyze(primary(net_income=-20., periods=5))
assert loss.cash_conversion is None
assert "cash_conversion_not_meaningful" in loss.unknowns
assert any("despite reported losses" in x for x in loss.positive_signals)

# Missing evidence stays neutral.
missing=AccountingQualityEngine().analyze({"verified_financials":{},"annual_history":{"periods":[]}})
assert missing.score == 50.0
assert missing.coverage == 0.0
assert not missing.red_flags

print("V3.7.1 accounting semantics/calibration: PASS")
print("2-period strong score:",strong2.score,"confidence:",strong2.confidence)
print("5-period strong score:",strong5.score,"confidence:",strong5.confidence)
print("loss cash conversion:",loss.cash_conversion)
