# Baby V11.0.1 — Decision Intelligence Hardening

Built on validated V10.6.2 + V11.0.

## Fixes
- Expectations engine now consumes V10.6.2 keys: revenue_growth_yoy, net_income_growth_yoy, ocf_growth_yoy, fcf_growth_yoy.
- SEC fundamentals now derives annual FCF YoY only from period-aligned OCF/CapEx pairs.
- Coverage split into pipeline, evidence, and decision-grade coverage. UNKNOWN domains cannot produce false 100% decision-grade coverage.
- Bull/bear evidence now carries strength, materiality, and deterministic weight.
- Severe risk/hard overrides retain decision caps and can outweigh multiple weak observations.
- Contradictions carry severity/materiality and impose deterministic penalty.
- ETF thesis is market-led; company fundamentals/valuation remain NOT_APPLICABLE and expectations are NOT_APPLICABLE.
- Thesis journal uses schema/version 11.0.1 and records changed evidence IDs on later snapshots.

## Authority
- AI factual authority: NONE
- AI scoring authority: 0%
- AI trade-level authority: 0%
- AI risk override authority: 0%
- AI execution authority: NONE
- Real-money execution: DISABLED
