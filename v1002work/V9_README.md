# BABY V9 — Agentic Investment Copilot

V9 replaces the brittle intent-first Ask Baby path with an AI planning layer over a strictly read-only investment tool registry.

## Authority model
- Nemotron: conversation understanding, intent/entity interpretation, research planning, evidence synthesis.
- Alpaca/read-only tools: current quotes, assets, broad/company news, market context.
- Baby production research: deterministic scores, risk, validation and trade-plan evidence.
- AI scoring authority: 0%.
- Chat execution authority: NONE.
- Real-money execution: DISABLED.

The V8.7.4 deterministic router remains only as an offline fallback when `NVIDIA_API_KEY` is unavailable.

## Freshness
Current questions must be tool-backed. Alpaca IEX is labeled as IEX, not SIP. News is returned with source/time metadata. Missing evidence stays unknown.
