# Baby V10.6.2 — XBRL Resolver Hardening

## Scope
Data-resolution hardening only. No DecisionEngine, unified-risk, TradePlan, R:R, execution-quality, position-sizing, or order-execution policy was relaxed.

## Changes
- Period-first SEC Company Facts alias resolution: economic period outranks concept preference.
- Expanded standardized revenue aliases, including `RevenueFromContractWithCustomerIncludingAssessedTax`, goods/services revenue, and `Revenues`.
- Expanded CapEx aliases, including productive-assets and selected PP&E variants.
- Current-period alias can no longer lose to an ancient preferred concept.
- Explicit selection audit on resolved duration/instant metrics: selected concept/taxonomy/form/accession/filed date, candidate count, period basis/end, selection reason.
- FCF still requires matching period basis and end date; incompatible inputs remain blocked.
- Broader CapEx aliases are disclosed with a review warning rather than silently treated as identical.
- ETF fundamentals and operating-company valuation now return `NOT_APPLICABLE` instead of `UNKNOWN`/missing-data semantics.
- Release version: 10.6.2.

## Regression coverage
`python v10_6_2_contract_test.py`

Covers NVDA stale CapEx contamination, current-period CapEx alias selection, CRWD revenue alias resolution, temporal FCF blocking, negative-earnings valuation, and ETF routing.
