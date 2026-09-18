# Decision Rules — V15.4

## Quantity ownership

Baby decides the deterministic trade plan and readiness state.

Baby may determine:
- setup
- entry
- invalidation
- Target 1
- Target 2
- risk/reward
- hard-risk constraints
- quote quality
- whether the setup is ready for review

The **user chooses the Alpaca PAPER order quantity**.

Baby does not calculate or display a recommended share count, proposed quantity, or proposed notional.

## Setup readiness

`WAITING` means the deterministic entry condition has not triggered.

`ELIGIBLE` / `SETUP_READY` means the setup, trade-quality, evidence, risk and quote gates passed and the plan is ready for human review.

Readiness is evaluated independently of position sizing.

## Submission

At submission time:
1. Baby recomputes the current deterministic setup.
2. The user supplies a positive quantity.
3. The user supplies the exact PAPER confirmation phrase.
4. Baby checks that the user-entered PAPER notional does not exceed available PAPER buying power/cash when those values are available.
5. The Alpaca PAPER broker receives the user-selected quantity.

`quantity_source = USER_SELECTED`

## Authority

AI scoring authority: `0%`

AI execution authority: `NONE`

Real-money execution: `DISABLED`
