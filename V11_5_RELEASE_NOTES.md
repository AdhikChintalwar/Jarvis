# Baby V11.5 — Historical Validation & Strategy Laboratory

Evaluation-only historical layer built on V11.0.1.

## Guarantees
- Signal at T can execute no earlier than the next market bar.
- Evidence/market/universe availability after signal time is a hard PIT failure and blocks the run.
- Incomplete survivorship, delisting, corporate-action, or macro-vintage coverage is surfaced, never hidden.
- Strategy thresholds are explicit experiment parameters; the lab never mutates V11 scoring.
- Calibration is diagnostic only. Untouched test data is not used for parameter selection.
- Experiment registry stores config, result and reproducibility hash.
- No brokerage/order API exists in this package. Real-money execution remains disabled.

## Important limitation
V11.5 provides the validation framework and contracts. A claim of point-in-time historical V11 performance is only valid when the caller supplies genuinely point-in-time reconstructed V11 decisions and complete-enough historical inputs. Current-day V11 reports must never be backfilled into historical dates.
