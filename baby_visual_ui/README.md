# BABY Investor Command Center

A complete visual UI shell for the Baby local investing system.

## What is included
- React + Vite dashboard
- FastAPI local bridge to the existing `investor` Python package
- Single-stock research workspace
- Verified-financial provenance/status/confidence table
- Technical indicator panel
- Risk panel
- Investment thesis panel
- Evidence-quality panel
- Scanner-style opportunity table
- Committee-ready panel
- Dark command-center design
- Mock/demo fallback so the UI can be developed without spending SEC/Nemotron calls

## Architecture
Browser (React) -> local FastAPI bridge -> existing `investor.StockAnalyzer`

The UI does not place trades. It is research/analysis only.

## Install
From your `Jarvis voice` project root:

```bash
unzip baby_visual_ui.zip
cd baby_visual_ui

# backend dependencies in your existing venv
pip install -r server/requirements.txt

# frontend
cd web
npm install
cd ..
```

## Run
Terminal 1, from `Jarvis voice` project root:
```bash
source .venv/bin/activate
uvicorn baby_visual_ui.server.app:app --reload --port 8766
```

Terminal 2:
```bash
cd baby_visual_ui/web
npm run dev
```

Open the Vite URL (normally localhost:5173).

The backend imports the existing `investor/` package from the project root. Keep `baby_visual_ui/` beside `investor/`.

## Modes
- LIVE: Analyze button calls your current StockAnalyzer.
- DEMO: if backend analysis fails, UI shows the error and retains demo data.
- Committee execution is intentionally not wired to a button yet; the UI shows committee readiness/evidence status without automatically spending Nemotron calls.

## Git
Do not commit this UI until you run it locally and approve the layout.
