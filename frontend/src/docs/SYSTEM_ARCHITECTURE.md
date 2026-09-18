# System Architecture

## High-level flow

```text
Market Scanner
    ↓
Production Research
    ↓
V11 Research Attractiveness / Thesis
    ↓
Deterministic Trade Plan
    ↓
Unified Risk + Portfolio Gate
    ↓
Execution-Quote Gate
    ↓
V12 Production Decision
    ↓
Monitored Setup
    ↓
Setup-Ready Notification
    ↓
Human Review
    ↓
Alpaca PAPER confirmation
```

## Frontend

The Baby frontend is a React/Vite application.

Production UI is deployed through Cloudflare Pages.

The frontend uses relative `/api/...` requests so the existing Cloudflare proxy path can route requests to the backend.

## Backend

The backend is FastAPI.

The production backend runs on the Oracle server and is supervised by systemd.

## Public routing

The production path is:

```text
Browser
→ Cloudflare Access / Pages
→ /api proxy
→ Baby backend
→ FastAPI
```

## Scheduler

Baby's research scheduler uses Eastern Time.

Current scheduled workflow includes pre-market research, post-open revalidation, recurring intraday refreshes and the afternoon scan.

Monitored symbols are revalidated in addition to the configured scanner top-N.

## Monitored setups

Monitored setups are stored durably and remain separate from Alpaca PAPER broker positions.

The stored monitoring snapshot intentionally does not need private account sizing information such as exact account equity or risk dollars.

## Alerts

In-app monitoring events and subscriber email notifications are separate from broker execution.

## Documentation

V15.3 stores product documentation in `frontend/src/docs/`.

The UI imports those markdown files directly, making the docs part of the same versioned codebase as the product.
