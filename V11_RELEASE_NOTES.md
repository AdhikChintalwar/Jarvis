# Baby V11 — Unified Investment Intelligence

Built on the validated V10.6.2 XBRL/temporal-integrity foundation.

Adds deterministic evidence graph, bull/bear thesis construction, contradictions/unknowns, expectations-vs-evidence analysis, Decision Engine V2, thesis state tracking, trade/exit context, portfolio evidence view, SQLite decision journal, analyst context, and historical/OOS validation hooks.

Safety invariants: missing evidence is UNKNOWN rather than bearish; hard risk caps research state; existing TradePlanAgent owns price levels; AI scoring/risk/execution authority remains zero/none; paper execution requires explicit confirmation; real money remains disabled.
