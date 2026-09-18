from __future__ import annotations

import importlib
import subprocess
import sys
from pathlib import Path

MODULES = {
    "fastapi": "FastAPI",
    "uvicorn": "Uvicorn",
    "pydantic": "Pydantic",
    "pydantic_settings": "Pydantic Settings",
    "dotenv": "python-dotenv",
    "requests": "Requests",
    "httpx": "HTTPX",
    "alpaca": "alpaca-py",
    "yfinance": "yfinance",
    "numpy": "NumPy",
    "pandas": "Pandas",
    "sklearn": "scikit-learn",
    "scipy": "SciPy",
    "bs4": "BeautifulSoup",
    "apscheduler": "APScheduler",
    "yaml": "PyYAML",
    "openai": "OpenAI",
    "jwt": "PyJWT",
    "cryptography": "cryptography",
}

failed = False

print("== Production dependency imports ==")
for module, label in MODULES.items():
    try:
        importlib.import_module(module)
        print(f"PASS  {label}")
    except Exception as exc:
        failed = True
        print(f"FAIL  {label}: {exc}")

print("\n== Baby backend import ==")
r = subprocess.run(
    [sys.executable, "-c", "import baby_ui_backend.app; print('PASS  baby_ui_backend.app')"],
    text=True,
    capture_output=True,
)
if r.stdout:
    print(r.stdout, end="")
if r.returncode:
    failed = True
    print(r.stderr)

print("\n== Key routes ==")
route_code = r"""
from baby_ui_backend.app import app
paths = app.openapi().get("paths", {})
required = [
    "/api/production/health",
    "/api/scheduler/status",
    "/api/monitor/jobs",
    "/api/monitor/sync",
    "/api/history/stock/{symbol}",
    "/api/history/portfolio",
]
for p in required:
    if p not in paths:
        raise SystemExit("MISSING "+p)
    print("PASS ", p)
"""
r = subprocess.run([sys.executable, "-c", route_code], text=True, capture_output=True)
if r.stdout:
    print(r.stdout, end="")
if r.returncode:
    failed = True
    print(r.stderr)

if failed:
    raise SystemExit("\nBABY CLOUD DEPENDENCY VALIDATION: FAIL")

print("\nBABY CLOUD DEPENDENCY VALIDATION: PASS")
