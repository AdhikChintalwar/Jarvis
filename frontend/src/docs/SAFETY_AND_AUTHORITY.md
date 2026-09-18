# Safety and Authority

## Current production boundaries

`REAL MONEY EXECUTION = DISABLED`

`AI EXECUTION AUTHORITY = NONE`

`AI SCORING AUTHORITY = 0%`

`AI RISK OVERRIDE AUTHORITY = 0%`

## AI may

- Explain Baby's exported evidence.
- Summarize research.
- Help the user understand abbreviations and logic.
- Help navigate the product.

## AI may not

- Override the deterministic research score.
- Override deterministic risk constraints.
- Invent missing evidence.
- Change the production quote authority.
- Submit a broker order.

## Setup-ready means review

A `SETUP_READY` or `ELIGIBLE` state means deterministic conditions are ready for human review.

It does not mean an order was automatically submitted.

## PAPER submission

The Alpaca integration is PAPER-only in the current architecture.

Research-driven PAPER submission recomputes server-side eligibility and quantity at submission time and requires explicit confirmation.

## Locked UI controls

V15.3 intentionally shows real-money execution, AI execution authority and automatic broker orders as locked controls instead of ordinary toggles.

A one-click interface toggle is not an appropriate boundary for enabling live financial execution.
