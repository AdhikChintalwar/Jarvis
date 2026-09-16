# BABY V8 — Research Cockpit + Live Market + Notifications

This is a UI/gateway overlay. It does **not** replace Baby's deterministic investor engine.

## Included
- React/Vite dark BABY research cockpit.
- Separate live-quote channel (WebSocket refresh default 10s).
- Quote quality labels: LIVE / DELAYED / STALE / UNKNOWN. The gateway never lies about quote quality.
- Research snapshot timestamp separate from quote timestamp.
- Full 14-stage research pipeline navigation.
- Metric definitions, abbreviations, formulas, inputs, thresholds, provenance, as-of, authority and verification status.
- PASS / REVIEW / FAIL / UNKNOWN / STALE / CONFLICT presentation.
- Auditable evidence/rule output; no hidden LLM chain-of-thought exposure.
- Trade plan / portfolio impact / historical validation panels.
- Alert database, severity, cooldown/deduplication and macOS notifications.
- AI scoring authority remains 0%; real-money execution remains disabled in this UI.

## Integration
After your existing investor run produces `result`:

```python
from baby_ui_backend import export_ui_report
export_ui_report("AAPL", result)
```

The compatibility adapter never invents missing fields. Missing modules show UNKNOWN until a richer V7/V7.5 adapter maps them.

For a real quote provider, inject a callable into `baby_ui_backend.app.quote_service.provider`. It must return a dict such as:

```python
{
  "price": 231.42,
  "change": 1.2,
  "change_pct": 0.52,
  "bid": 231.40,
  "ask": 231.44,
  "volume": 1234567,
  "day_high": 233.10,
  "day_low": 228.90,
  "timestamp": "...",
  "quality": "LIVE", # only if provider contract truly is live
  "provider": "YOUR_PROVIDER"
}
```

Do not label Yahoo daily/prototype data as LIVE.

## Run

```bash
source .venv/bin/activate
pip install -r requirements-v8.txt
./run_v8.sh
```

Open http://127.0.0.1:5173

## Next integration boundary
The current package is intentionally provider-neutral because the exact V7.5 runtime object/API is not embedded in this overlay. Map the V7.5 result into `ResearchReport` rather than changing V7.5 scoring logic.
