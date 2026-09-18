# Pipeline Logic

This document explains the purpose and logic of Baby's major production research stages in simple terms.

The code remains the source of truth for exact formulas, thresholds and version-specific behavior. This document describes the intended logic without inventing values that are not explicitly exported by the current pipeline.

## 1. Discovery / Scanner

### Data
Market symbols and scanner inputs such as price/volume behavior and other configured discovery features.

### Logic
The scanner searches for stocks that meet the current discovery profile. Discovery narrows a large market universe into research candidates.

### Result
A candidate list.

### Important
A scanner candidate is not a recommendation and is not automatically eligible for a PAPER order.

## 2. Market Data / Price History

### Data
OHLCV: Open, High, Low, Close and Volume.

### Logic
Historical bars are the raw input used to calculate technical indicators and price relationships.

### Result
A normalized price-history packet used by later stages.

### Important
Insufficient or missing history should reduce coverage or produce `UNKNOWN`; it should not be invented.

## 3. Technical Analysis

### Data
Price history, volume and current price context.

### Logic
Baby calculates deterministic technical evidence such as moving averages, momentum measures and price relationships. Current production code may export items such as SMA, EMA and RSI.

### Result
Technical evidence that may be positive, negative, review-required or unresolved.

### Important
Technical evidence is one part of the research model. It does not independently create an order.

## 4. Fundamentals

### Data
Company financial statement data available to the production pipeline.

### Logic
Baby evaluates available business/financial metrics and whether the evidence is complete enough to support the research model.

### Result
Structured fundamental evidence plus source/coverage information.

## 5. Financial Health

### Data
Available financial statement relationships such as profitability, cash generation, liquidity, debt and related measures.

### Logic
Baby checks financial strength and weaknesses using deterministic calculations from available data.

### Result
Positive evidence, negative evidence, conflicts and unknowns.

## 6. Accounting Quality

### Data
Reported financial results and cash-flow/balance-sheet relationships.

### Logic
Baby checks whether important reported relationships are internally consistent enough for research use. The stage is an evidence-quality assessment, not an allegation of misconduct.

### Result
Evidence-quality findings such as PASS, REVIEW, FAIL or UNKNOWN where supported by the production pipeline.

## 7. Valuation

### Data
Available company financial metrics, market price and valuation inputs.

### Logic
Baby compares the current market value/price context with available business metrics using the configured valuation model.

### Result
A deterministic valuation assessment such as favorable, demanding or unresolved according to the current pipeline output.

### Important
Valuation is evidence, not a standalone timing signal.

## 8. SEC / Corporate Filings

### Data
Available SEC filing and corporate-event context.

### Logic
Baby looks for filing evidence that may matter to the thesis, such as financing, material events or disclosures. Registration language is not automatically treated as completed dilution.

### Result
Structured filing evidence or `UNKNOWN` when evidence is unavailable.

## 9. Catalysts / Events / News

### Data
Company-specific news/event evidence from configured sources.

### Logic
Baby classifies available events and includes them as research context.

### Result
Catalyst/event evidence with a cautious causality boundary.

### Important
Headline timing does not prove that the headline caused a price move. Baby uses `NOT_ESTABLISHED` when causality is not established.

## 10. Macro / Market Regime

### Data
Configured broad-market and macro context.

### Logic
Baby evaluates the environment around the company rather than treating the stock in isolation.

### Result
Context that may affect risk or research interpretation.

## 11. Advanced Market Intelligence

### Data
Additional market evidence exported by the production research system.

### Logic
This stage combines configured higher-level market evidence without giving an LLM authority to invent facts or scoring.

### Result
Structured evidence feeding the deterministic thesis/risk layers.

## 12. Unified Risk

### Data
Research findings, market conditions and configured risk constraints.

### Logic
Baby combines risk evidence into one deterministic risk layer. Hard-risk conditions may constrain a candidate even when other evidence looks attractive.

### Result
Risk level, constraints and any hard-risk override.

### Authority
AI risk-override authority is 0.

## 13. Research Attractiveness / V11 Decision

### Data
Evidence produced by the research stages.

### Logic
Baby applies deterministic stage weights, evidence adjustments and contradiction penalties according to the production V11 model.

### Result
A research-attractiveness score, confidence/coverage values and a deterministic decision state.

### Important
The score is not a probability that the price will rise and is not a buy/sell recommendation.

## 14. Thesis State

### Data
Current research result compared with available previous research.

### Logic
Baby tracks whether the thesis evidence is stable, strengthening, weakening or constrained/broken according to deterministic changes.

### Result
A thesis-state label and changed evidence where available.

## 15. Trade Plan

### Data
Research result, current price/technical structure and deterministic risk rules.

### Logic
Baby builds possible pullback and/or breakout structures with planned entry, invalidation and targets.

### Result
A trade plan with setup status.

Typical states include waiting for a pullback/breakout or an active setup state.

## 16. Position Sizing / PAPER Proposal

### Data
Trade-plan risk structure, current execution-grade quote and Alpaca PAPER account constraints.

### Logic
The server recomputes quantity and proposal eligibility. Browser-supplied quantity is not trusted for research-driven Alpaca PAPER submission.

### Result
`WAITING` or `ELIGIBLE`, plus deterministic sizing fields when the structure is valid.

### Important
Eligibility does not submit an order.

## 17. Portfolio Gate

### Data
PAPER account context and proposed exposure.

### Logic
Baby checks portfolio/account constraints before a production proposal can pass.

### Result
PASS/BLOCKED or equivalent deterministic gate output.

## 18. Execution Quote Gate

### Data
Current production quote.

### Logic
The quote is checked for freshness and market-quality requirements such as valid bid/ask and acceptable spread according to configured thresholds.

### Production authority
Alpaca market data / IEX is used for the production execution-grade quote path in the current setup. Other research/display sources must not silently replace the production quote authority.

### Result
PASS or a blocking/review condition.

## 19. V12 Production Decision

### Data
Research decision, trade plan, quote validation, risk and portfolio gates.

### Logic
Baby combines deterministic production gates. Any required blocking condition prevents the candidate from becoming a ready PAPER proposal.

### Result
Production status and bridge failures explaining why it passed or did not pass.

## 20. Monitored Setup

### Data
Latest deterministic proposal/production decision for a symbol you asked Baby to monitor.

### Logic
Baby stores a sanitized monitoring snapshot and revalidates monitored symbols on the operating schedule.

Private sizing/account values are not required in the monitored setup card.

### Result
A current monitoring state such as waiting or setup ready.

## 21. Setup-Ready Transition

### Logic
A meaningful transition is `WAITING → SETUP_READY`.

Continued `SETUP_READY → SETUP_READY` should not create another setup-ready transition notification.

If a setup leaves readiness and later returns to readiness, Baby may create a new notification.

## 22. Human Review / Alpaca PAPER

A setup-ready state tells the user to review the deterministic plan.

An Alpaca PAPER submission requires explicit confirmation.

The current system does not add automatic live-money execution.
