# Data Sources

This file explains the source-authority rules that matter to Baby. Exact providers used by individual research stages can evolve; the research output/source labels and production code remain authoritative.

## Production execution quote

**Current authority:** Alpaca market data, using the configured IEX path.

**Purpose:** Current production quote validation and PAPER proposal gating.

**Requirements:** The quote must satisfy configured freshness and quality checks. Invalid bid/ask, crossed quotes, stale timestamps or excessive spread can prevent production eligibility.

**Fallback rule:** A research/display quote must not silently become production execution authority.

## Historical price / OHLCV

**Purpose:** Technical calculations, charts and research evidence.

The configured production research pipeline provides historical market bars. Individual research artifacts should expose source information when available.

## Financial statements / company fundamentals

**Purpose:** Fundamentals, financial health, accounting-quality and valuation research.

Baby uses the configured financial-data pipeline and preserves unresolved evidence as UNKNOWN.

The exact provider and source authority should be read from current production evidence rather than assumed from this document.

## SEC filings

**Authority:** SEC/corporate filing evidence available to the production pipeline.

**Purpose:** Material filings, financing context and corporate-event evidence.

**Important:** Filing language is interpreted cautiously. Registration language alone is not automatically treated as completed dilution.

## Company news/events

**Current configured news path:** Alpaca News where available.

**Purpose:** Company-specific catalyst/event context.

**Causality:** Headline timing does not prove price causality. Baby can label causality `NOT_ESTABLISHED`.

## Macro / market context

**Purpose:** Broad environment/context for research and risk.

The exact current macro source should be taken from the production research evidence/source labels.

## Alpaca PAPER account

**Purpose:** Simulated equity, cash, buying power, PAPER positions and PAPER orders.

This is separate from Baby Monitored Setups.

## Email

**Current transport:** Configured SMTP relay.

Email is used only for research/setup notifications. It has no broker execution authority.

## Source-authority principles

- Primary/production evidence is not replaced silently by a convenient fallback.
- Display data and execution-grade data are different concepts.
- Missing evidence remains UNKNOWN.
- Source timestamps matter.
- Quote freshness matters.
- A provider failure should be visible instead of being hidden behind invented data.
