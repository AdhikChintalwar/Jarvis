# Baby V10 — Investment Intelligence & Research-to-Trade Flow

V10 expands the stable V9.1.1 agent without transferring scoring or execution authority to AI.

## New capabilities
- Full deterministic research-flow projection.
- Research → Decision → TradePlan → Position/Paper Proposal → Exit Policy.
- Explicit pullback and breakout scenario semantics.
- Deterministic R:R calculation for production targets.
- Partial-exit/trailing/thesis/event/time-exit policy semantics.
- Agent tools for full Baby investment flow and trade-plan explanation.
- Missing/invalid setup remains WAIT/UNKNOWN; no fabricated entry.

## Authority
AI scoring: 0%. AI execution: NONE. Real money: DISABLED.

## Endpoints
- `GET /api/v10/research/{symbol}/full-flow`
- `GET /api/v10/research/{symbol}/exit-policy`

Run `python v10_contract_test.py` after the existing V8/V9 contracts.
