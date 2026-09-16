from investor import StockAnalyzer

from investor.abnormal_volume import (
    AbnormalVolumeEngine,
)

from investor.sec_filing_analyzer import (
    SECFilingAnalyzer,
)

from investor.trade_plan import (
    TradePlanEngine,
)


ticker = "TJGC"


print()
print(
    "Running Baby Investor V3 tests..."
)
print()


analyzer = StockAnalyzer()

report = analyzer.analyze(
    ticker
)


history = (
    analyzer.provider
    .get_history(
        ticker,
        period="1y",
        interval="1d",
    )
)


print()
print("=" * 70)
print("ABNORMAL VOLUME")
print("=" * 70)

volume_engine = (
    AbnormalVolumeEngine()
)

volume = volume_engine.analyze(
    history
)

print(
    "Current RVOL:",
    volume.current_relative_volume,
)

print(
    "5-day average RVOL:",
    volume.average_relative_volume_5d,
)

print(
    "Abnormal days:",
    volume.abnormal_days_20d,
)

print(
    "Extreme-volume days:",
    volume.extreme_volume_days_20d,
)

print(
    "Bullish events:",
    volume.bullish_volume_events,
)

print(
    "Bearish events:",
    volume.bearish_volume_events,
)

print(
    "Accumulation score:",
    volume.accumulation_score,
)

print(
    "Signal:",
    volume.volume_signal,
)


print()
print("=" * 70)
print("DEEP SEC")
print("=" * 70)


sec_engine = (
    SECFilingAnalyzer()
)

deep_sec = sec_engine.analyze(
    report["sec"]
)

print(
    "Filings scanned:",
    deep_sec.filings_scanned,
)

print(
    "Dilution score:",
    deep_sec.dilution_score,
)

print(
    "Dilution risk:",
    deep_sec.dilution_risk,
)

for summary in (
    deep_sec.summary
):

    print(
        "•",
        summary,
    )


for finding in (
    deep_sec.all_findings[:12]
):

    print()

    print(
        f"{finding.filing_date} | "
        f"{finding.filing_form} | "
        f"{finding.severity.upper()} | "
        f"{finding.phrase} | "
        f"score={finding.score:.1f}"
    )

    print(
        "Context:",
        finding.context[:500],
    )

print(
    "Dilution score:",
    deep_sec.dilution_score,
)

print(
    "Dilution risk:",
    deep_sec.dilution_risk,
)

print(
    "Distress score:",
    deep_sec.distress_score,
)

print(
    "Distress risk:",
    deep_sec.distress_risk,
)


trade_engine = (
    TradePlanEngine()
)

trade = trade_engine.build(

    history=history,

    technical=(
        report[
            "technical"
        ]
    ),

    risk=(
        report[
            "risk"
        ]
    ),

    thesis=(
        report[
            "thesis"
        ]
    ),
)


print(
    "Status:",
    trade.setup_status,
)

print(
    "Current price:",
    trade.current_price,
)

print(
    "Support 1:",
    trade.support_1,
)

print(
    "Support 2:",
    trade.support_2,
)

print(
    "Resistance 1:",
    trade.resistance_1,
)

print(
    "Resistance 2:",
    trade.resistance_2,
)

print(
    "Preferred entry:",
    trade.preferred_entry_low,
    "-",
    trade.preferred_entry_high,
)

print(
    "Stop:",
    trade.stop_loss,
)

print(
    "Target 1:",
    trade.target_1,
)

print(
    "Target 2:",
    trade.target_2,
)

print(
    "R/R Target 1:",
    trade.risk_reward_1,
)

print(
    "R/R Target 2:",
    trade.risk_reward_2,
)


print()
print("NOTES")

for note in trade.notes:

    print(
        "⚠",
        note,
    )


print()
print("=" * 70)