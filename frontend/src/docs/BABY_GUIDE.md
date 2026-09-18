# Baby Guide

Baby V15.3 is organized around a simple workflow: discover a stock, research it, validate the evidence, build a deterministic plan, monitor the setup, and review any PAPER action yourself.

## Home

Home is the daily overview. Use it to answer: What is Baby doing, what changed, and what deserves attention?

It may show scanner activity, research candidates, monitoring events and shortcuts to deeper research. Home is a summary; it is not the final authority for a trade plan.

## Ideas

Ideas contains stocks surfaced by Baby's discovery/scanner workflow.

A stock appearing in Ideas means it met the discovery rules used by the current scanner. It does **not** mean the stock is a recommendation, an approved PAPER order or an active position.

Open a symbol in Stock Research before interpreting the candidate.

## Stock Research

Stock Research is the detailed evidence view for one symbol.

The page separates research into pipeline stages. Each stage exposes available metrics, source information, deterministic reasoning and unresolved evidence. Missing evidence should remain `UNKNOWN` rather than being silently treated as positive or negative.

The research score represents **research attractiveness** inside Baby's deterministic model. It is not a prediction of future returns.

## Trade Plan

The Trade Plan is produced from deterministic research and price/setup rules.

Typical fields include current setup, current price, pullback zone, breakout trigger, planned entry, invalidation, Target 1, Target 2 and risk/reward ratios.

A plan may exist while the setup is still waiting.

## Check Alpaca Paper Setup

This action recomputes the current deterministic PAPER proposal against current Alpaca PAPER account constraints and the execution-grade quote path.

In V15.2+, checking the setup also adds the symbol to **Monitored Setups**.

`WAITING` means the required entry/setup conditions are not active.

`SETUP READY` or `ELIGIBLE` means Baby's deterministic conditions are ready for human review. It does not submit an order.

## Portfolio

Portfolio separates two different concepts.

**Monitored Setups** are research plans Baby is watching. They are not broker positions.

**Alpaca PAPER Positions** are simulated holdings that actually exist at the Alpaca PAPER broker.

**Alpaca PAPER Orders** are simulated broker orders.

A monitored setup stays separate from the PAPER portfolio until an explicit PAPER submission occurs and the broker fills the order.

## Alerts

Alerts contains important system and monitoring events.

Setup-ready notifications are intended to tell you that a deterministic setup changed state and needs review. Email alerts are research notifications only.

Repeated observations of the same ready state should not create unnecessary duplicate setup-ready messages. If a setup leaves readiness and later becomes ready again, that is a new transition.

## Settings & Status

Settings & Status answers the operational question: Is Baby working?

It shows scheduler state, recent scan/revalidation times, monitored setup count, current symbol being checked, Alpaca PAPER connectivity, email readiness and recent monitoring events.

The page also contains safe interface preferences such as Developer Tools visibility, automatic status refresh and whether the sidebar clock shows seconds.

Safety-critical controls remain locked.

## Documentation

Documentation is the plain-language reference for the product.

The documentation files live with the source code so important product changes can update the explanation in the same Git commit.

## About Baby

About explains Baby's purpose, workflow, version and authority boundaries.

## Developer Tools

Developer Tools are hidden by default because they are primarily useful for development and diagnosis.

**Raw Scanner** shows low-level scanner output.

**Backtests** are used to inspect historical validation when research or rule changes need testing.

**Automations** exposes scheduling/automation internals.

Enable Developer Tools from Settings & Status when you need them.

## Ask Baby

Ask Baby is an explanation interface. It may summarize or explain Baby's available data, but it does not have broker execution authority.

## Important distinction

Discovery is not readiness. Readiness is not execution. A PAPER position is not real money. Baby keeps these states separate on purpose.
