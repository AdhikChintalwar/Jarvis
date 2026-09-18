# Troubleshooting — V15.4

## Why doesn't Baby show a share quantity?

That is intentional. Baby determines the trade plan and setup readiness. You choose the Alpaca PAPER quantity.

## Why can a setup be READY without a proposed notional?

Quantity and notional are no longer readiness gates. They only exist after you enter a quantity for a PAPER submission.

## Why is a setup WAITING?

The deterministic entry condition has not triggered yet. Check the pullback zone/breakout trigger in Stock Research → Trade Plan.

## Why is a monitored setup not an Alpaca position?

Monitoring is research state. A PAPER position exists only after you explicitly submit a PAPER order and Alpaca fills it.

## Where is production data stored?

On the Oracle VM under `/opt/baby/data/`.

## What does the V15.4 backup script protect?

It backs up all SQLite databases under the data directory using SQLite's backup API, copies non-DB operational artifacts, creates SHA-256 checksums and a manifest, runs `PRAGMA quick_check`, applies retention, and optionally supports an off-VM rclone destination.
