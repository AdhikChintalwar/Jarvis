# BABY Investor — Production Candidate

This package consolidates V10.6.2, V11.0.1, V11.5 and the existing V5–V7.5 PIT/backtest infrastructure into one paper-trading production candidate.

## New production hardening
- Durable SQLite production ledger with schema migration table and audit log.
- Idempotent proposal creation. Repeated requests with the same idempotency key return the original proposal.
- Deterministic portfolio admission gate: max positions, position %, sector %, correlated exposure, portfolio risk, single-trade risk and minimum cash reserve.
- ETF-specific thesis engine. Company fundamentals/valuation remain NOT_APPLICABLE for ETFs.
- Position-management engine producing exit/partial-exit proposals for invalidation, targets, hard-risk and broken thesis. It never executes.
- Provider-health gate that fails closed for execution when no primary provider is healthy.
- Persistent monitoring store for score changes, hard-risk activation and thesis deterioration.
- V11.5 historical adapter retains point-in-time availability audit, signal-T to next-bar execution, walk-forward diagnostic, calibration and experiment registry.
- Production startup guard refuses any configuration attempting to enable real-money execution.

## Authority contract
- Verified evidence: authoritative according to source hierarchy.
- Baby deterministic calculations and Decision Engine: authoritative for Baby research.
- AI factual authority: NONE.
- AI scoring authority: 0%.
- AI price-level authority: 0%.
- AI risk-override authority: 0%.
- AI execution authority: NONE.
- Paper execution: explicit user confirmation only.
- Real-money execution: DISABLED.

## Historical claims
The production candidate does not claim a historical V11 track record unless PIT availability, universe/delisting coverage, corporate actions and macro vintages satisfy the audit. Incomplete inputs remain limitations; automatic production retuning is disabled.

## New API surfaces
- GET `/api/production/health`
- POST `/api/production/portfolio/gate`
- POST `/api/production/proposals/{symbol}`
- POST `/api/production/positions/evaluate`
- POST `/api/production/etf/{symbol}/thesis`

These endpoints are research/paper infrastructure only and expose no live brokerage execution.
